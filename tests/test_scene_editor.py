import base64
import copy
import http.client
import json
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lightshow.app import Config, LightShowApplication
from lightshow.layout import validate_layout
from lightshow.protocols import ddp_packets, sacn_packets


def example_layout():
    return {"name": "Editable display", "fixtures": [
        {"id": "roofline", "name": "Roof", "startChannel": 1, "pixels": [[0, 2, 0], [1, 2, 0]]},
        {"id": "custom", "name": "Custom", "startChannel": 10, "pixels": [[3, 1, 0]]}]}


class SceneValidationTests(unittest.TestCase):
    def test_legacy_defaults_filter_bindings_and_explicit_scene_roundtrips(self):
        layout = validate_layout(example_layout())
        scene = layout["scene"]
        self.assertEqual(scene["objects"][0]["fixtureIds"], ["roofline"])
        self.assertEqual(scene["environment"]["skyColor"], "#152238")
        self.assertEqual(validate_layout(layout), layout)
        layout["scene"]["objects"] = []
        self.assertEqual(validate_layout(layout)["scene"]["objects"], [])

    def test_invalid_scenes_and_universe_ranges_are_rejected(self):
        mutations = [
            lambda layout: layout["scene"]["objects"][0].update(position=[0, float("nan"), 0]),
            lambda layout: layout["scene"]["objects"][0].update(scale=[1, 0, 1]),
            lambda layout: layout["scene"]["objects"][0].update(rotation=[0, 361, 0]),
            lambda layout: layout["scene"]["objects"][0].update(color="red"),
            lambda layout: layout["scene"]["objects"][0].update(type="javascript"),
            lambda layout: layout["scene"]["objects"][1].update(id="house"),
            lambda layout: layout["scene"]["objects"][1].update(fixtureIds=["roofline"]),
            lambda layout: layout["scene"]["objects"][0].update(fixtureIds=["missing"]),
            lambda layout: layout["scene"]["environment"].update(exposure=4),
            lambda layout: layout["scene"]["environment"].update(glow="yes"),
            lambda layout: layout.update(universeSize=511),
            lambda layout: layout.update(startUniverse=63999, channelCount=1026),
            lambda layout: layout["fixtures"][0].update(pixelCount=999),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                layout = validate_layout(example_layout())
                mutate(layout)
                with self.assertRaises(ValueError):
                    validate_layout(layout)


class SceneEditorAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.layout_file, self.unreal_file = root / "layout.json", root / "unreal.json"
        self.layout_file.write_text(json.dumps(example_layout()), encoding="utf-8")
        self.unreal_file.write_text("{}", encoding="utf-8")
        self.app = LightShowApplication(Config(port=0, ddp_port=0, sacn_port=0, relay_enabled=False,
                                               layout=self.layout_file, unreal_layout=self.unreal_file)).start()
        self.base = f"http://127.0.0.1:{self.app.config.port}"

    def tearDown(self):
        self.app.stop()
        self.temporary.cleanup()

    def get(self, route="/api/layout"):
        with urlopen(self.base + route, timeout=3) as response:
            return json.loads(response.read())

    def post(self, layout, revision=None, headers=None):
        body = {"layout": layout, "revision": layout["revision"] if revision is None else revision}
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        request = Request(self.base + "/api/layout", json.dumps(body).encode(), request_headers, method="POST")
        with urlopen(request, timeout=3) as response:
            return json.loads(response.read())

    def wait_rgb(self, expected):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            frame = self.get("/api/frame")
            if base64.b64decode(frame["rgb"]) == expected:
                return frame
            time.sleep(.015)
        self.fail("New mapping never produced the expected live RGB frame")

    def test_save_backup_unreal_sync_restart_and_stale_browser(self):
        original_disk = self.layout_file.read_bytes()
        original = self.get()
        changed = copy.deepcopy(original)
        changed["name"] = "Saved yard"
        changed["scene"]["objects"][0]["position"] = [2, 0, -3]
        changed["scene"]["environment"]["snowfall"] = False
        changed["startUniverse"], changed["universeSize"] = 23, 512
        saved = self.post(changed)
        self.assertEqual(saved["layout"]["revision"], original["revision"] + 1)
        self.assertEqual(saved["status"]["layoutRevision"], saved["layout"]["revision"])
        self.assertTrue(saved["unrealSync"]["saved"])
        self.assertEqual(self.layout_file.read_bytes(), self.unreal_file.read_bytes())
        self.assertEqual(self.layout_file.with_suffix(".json.bak").read_bytes(), original_disk)
        self.assertNotIn("revision", json.loads(self.layout_file.read_text(encoding="utf-8")))
        restarted = LightShowApplication(Config(layout=self.layout_file, unreal_layout=None))
        self.assertEqual(restarted.layout, self.app.layout)
        self.assertEqual(restarted.config.start_universe, 23)
        self.assertEqual(restarted.config.universe_size, 512)
        active_disk = self.layout_file.read_bytes()
        with self.assertRaises(HTTPError) as error:
            self.post(original)
        self.assertEqual(error.exception.code, 409)
        error.exception.close()
        self.assertEqual(self.layout_file.read_bytes(), active_disk)
        self.assertEqual(self.get(), saved["layout"])

    def test_invalid_layout_origin_and_oversize_body_do_not_mutate(self):
        original, disk = self.get(), self.layout_file.read_bytes()
        invalid = copy.deepcopy(original)
        invalid["scene"]["objects"][0]["fixtureIds"] = ["unknown"]
        with self.assertRaises(HTTPError) as error:
            self.post(invalid)
        self.assertEqual(error.exception.code, 400)
        error.exception.close()
        with self.assertRaises(HTTPError) as error:
            self.post(original, headers={"Origin": "https://example.com"})
        self.assertEqual(error.exception.code, 403)
        error.exception.close()
        connection = http.client.HTTPConnection("127.0.0.1", self.app.config.port, timeout=3)
        connection.request("POST", "/api/layout", body=b"{}", headers={
            "Content-Type": "application/json", "Content-Length": "8000001"})
        response = connection.getresponse()
        self.assertEqual(response.status, 400)
        response.read()
        connection.close()
        self.assertEqual(self.layout_file.read_bytes(), disk)
        self.assertEqual(self.get(), original)
        self.assertFalse(self.layout_file.with_suffix(".json.bak").exists())

    def test_failed_primary_replace_keeps_active_file_and_runtime(self):
        original, disk = self.get(), self.layout_file.read_bytes()
        changed = copy.deepcopy(original)
        changed["name"] = "Could not save"
        import os
        original_replace = os.replace

        def failed_replace(source, target):
            if Path(target) == self.layout_file:
                raise OSError("simulated disk failure")
            return original_replace(source, target)

        with patch("lightshow.app.os.replace", side_effect=failed_replace):
            with self.assertRaises(HTTPError) as error:
                self.post(changed)
            self.assertEqual(error.exception.code, 500)
            error.exception.close()
        self.assertEqual(self.get(), original)
        self.assertEqual(self.layout_file.read_bytes(), disk)
        self.assertEqual(list(self.layout_file.parent.glob("*.tmp")), [])

    def test_external_file_edit_conflicts_without_backup_or_runtime_changes(self):
        original = self.get()
        external = copy.deepcopy(original)
        external["name"] = "External editor change"
        external_bytes = json.dumps(external).encode("utf-8")
        self.layout_file.write_bytes(external_bytes)
        with self.assertRaises(HTTPError) as error:
            self.post(original)
        self.assertEqual(error.exception.code, 409)
        self.assertIn("restart the server", json.loads(error.exception.read())["error"])
        error.exception.close()
        self.assertEqual(self.layout_file.read_bytes(), external_bytes)
        self.assertEqual(self.get(), original)
        self.assertFalse(self.layout_file.with_suffix(".json.bak").exists())
        self.assertEqual(self.unreal_file.read_text(), "{}")
        restarted = LightShowApplication(Config(layout=self.layout_file, unreal_layout=None))
        self.assertEqual(restarted.layout["name"], "External editor change")

    def test_old_browser_cannot_overwrite_newly_loaded_layout_after_restart(self):
        stale = self.get()
        external = copy.deepcopy(stale)
        external["name"] = "Changed while server was stopped"
        external_bytes = json.dumps(external).encode("utf-8")
        self.app.stop()
        self.layout_file.write_bytes(external_bytes)
        backup = self.layout_file.with_suffix(".json.bak")
        backup.write_bytes(b"Keep the existing backup")
        # Choose a distinct startup seed deterministically; the production source
        # uses secrets so independently restarted processes do not reuse token 1.
        with patch("lightshow.app.secrets.randbelow", return_value=stale["revision"] % (2**52 - 1)):
            self.app = LightShowApplication(Config(port=0, ddp_port=0, sacn_port=0, relay_enabled=False,
                                                   layout=self.layout_file, unreal_layout=self.unreal_file)).start()
        self.base = f"http://127.0.0.1:{self.app.config.port}"
        current = self.get()
        self.assertNotEqual(current["revision"], stale["revision"])
        self.assertTrue(1 <= current["revision"] <= 2**53 - 1)
        with self.assertRaises(HTTPError) as error:
            self.post(stale)
        self.assertEqual(error.exception.code, 409)
        error.exception.close()
        self.assertEqual(self.layout_file.read_bytes(), external_bytes)
        self.assertEqual(backup.read_bytes(), b"Keep the existing backup")
        self.assertEqual(self.unreal_file.read_text(), "{}")
        self.assertEqual(self.get(), current)

    def test_revision_token_rejects_nonintegers_and_unsafe_javascript_values(self):
        original, disk = self.get(), self.layout_file.read_bytes()
        for revision in (True, 1.0, 0, -1, 2**53):
            with self.subTest(revision=revision), self.assertRaises(HTTPError) as error:
                self.post(original, revision=revision)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        self.assertEqual(self.get(), original)
        self.assertEqual(self.layout_file.read_bytes(), disk)
        self.assertFalse(self.layout_file.with_suffix(".json.bak").exists())

    def test_channel_span_edits_rebuild_buffers_and_accept_both_protocols(self):
        layout = self.get()
        layout["fixtures"][1]["startChannel"] = 1021
        layout["fixtures"][1]["pixels"].extend([[4 + index / 100, 1, 0] for index in range(1000)])
        layout["fixtures"][1].pop("pixelCount")
        layout.pop("pixelCount")
        layout.pop("channelCount")
        self.assertGreater(len(json.dumps({"layout": layout, "revision": layout["revision"]})), 16384)
        result = self.post(layout)
        self.assertEqual(result["layout"]["channelCount"], 4023)
        self.assertEqual(result["status"]["universeCount"], 8)
        self.assertEqual(len(self.app.live_rgb), 4023)
        self.assertEqual(self.app.mapping[-1][0], 4020)
        self.app.control({"mode": "live", "playing": True, "brightness": 1})
        expected = bytes((index * 7 + 9) % 256 for index in range(4023))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            for packet, _ in ddp_packets(expected, 1):
                sender.sendto(packet, ("127.0.0.1", self.app.config.ddp_port))
            self.assertEqual(self.wait_rgb(expected)["activeProtocol"], "ddp")
            expected = bytes((index * 11 + 19) % 256 for index in range(4023))
            for packet in sacn_packets(expected, sequence=1, cid=b"s" * 16):
                sender.sendto(packet, ("127.0.0.1", self.app.config.sacn_port))
            self.assertEqual(self.wait_rgb(expected)["activeProtocol"], "sacn")
        self.assertTrue(self.app.receivers["ddp"]["error"] is None)
        self.assertTrue(self.app.receivers["sacn"]["error"] is None)

    def test_multicast_join_failure_rolls_back_memberships_before_writing(self):
        original, disk = self.get(), self.layout_file.read_bytes()
        changed = copy.deepcopy(original)
        changed["startUniverse"], changed["channelCount"] = 3, 1026
        operations = []

        def membership(universe, join=True):
            operations.append((universe, join))
            if universe == 4 and join:
                raise OSError("simulated multicast join failure")

        with patch.object(self.app, "_multicast_membership", side_effect=membership):
            with self.assertRaises(HTTPError) as error:
                self.post(changed)
            self.assertEqual(error.exception.code, 500)
            error.exception.close()
        self.assertEqual(operations, [(3, True), (4, True), (3, False)])
        self.assertEqual(self.get(), original)
        self.assertEqual(self.layout_file.read_bytes(), disk)

    def test_unreal_copy_failure_is_reported_after_successful_primary_save(self):
        changed = self.get()
        changed["name"] = "Primary saved"
        import os
        original_replace = os.replace

        def failed_copy(source, target):
            if Path(target) == self.unreal_file:
                raise OSError("simulated Unreal copy failure")
            return original_replace(source, target)

        with patch("lightshow.app.os.replace", side_effect=failed_copy):
            result = self.post(changed)
        self.assertEqual(self.get()["name"], "Primary saved")
        self.assertEqual(json.loads(self.layout_file.read_text())["name"], "Primary saved")
        self.assertFalse(result["unrealSync"]["saved"])
        self.assertIn("copy failure", result["unrealSync"]["error"])


if __name__ == "__main__":
    unittest.main()
