#!/usr/bin/env python3
"""Launch the Christmas light show preview and its xLights/Unreal UDP bridge."""

import argparse
from pathlib import Path
import sys
import time

from lightshow.app import Config, LightShowApplication


def arguments():
    defaults = Config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=defaults.host, help="HTTP bind address (default: loopback)")
    parser.add_argument("--port", type=int, default=defaults.port, help="HTTP port (default: 8080)")
    parser.add_argument("--udp-host", default=defaults.udp_host, help="UDP bind address; use 0.0.0.0 for LAN input")
    parser.add_argument("--ddp-port", type=int, default=defaults.ddp_port)
    parser.add_argument("--sacn-port", type=int, default=defaults.sacn_port)
    parser.add_argument("--sacn-multicast", action="store_true", help="Join configured sACN universes on IPv4 multicast")
    parser.add_argument("--multicast-interface", default=defaults.multicast_interface, help="Local IPv4 interface for multicast membership")
    parser.add_argument("--universe-size", type=int, choices=(510, 512), default=defaults.universe_size,
                        help="Override saved sACN slots per universe (legacy default: 510)")
    parser.add_argument("--start-universe", type=int, default=defaults.start_universe,
                        help="Override saved first sACN universe (legacy default: 1)")
    parser.add_argument("--relay-host", default=defaults.relay_host)
    parser.add_argument("--relay-port", type=int, default=defaults.relay_port, help="Unreal DDP receive port (default: 4049)")
    parser.add_argument("--no-relay", action="store_true")
    parser.add_argument("--no-unreal-sync", action="store_true",
                        help="Save only the active layout; do not copy it into the bundled Unreal project")
    parser.add_argument("--layout", type=Path, default=defaults.layout)
    parser.add_argument("--fps", type=float, default=defaults.fps)
    args = parser.parse_args()
    options = vars(args)
    options["relay_enabled"] = not options.pop("no_relay")
    if options.pop("no_unreal_sync"):
        options["unreal_layout"] = None
    return Config(**options)


def main():
    try:
        app = LightShowApplication(arguments()).start()
    except (ValueError, OSError) as error:
        print(f"Could not start preview: {error}", file=sys.stderr)
        return 1
    url_host = "localhost" if app.config.host in ("0.0.0.0", "127.0.0.1") else app.config.host
    print(f"Christmas Lights preview: http://{url_host}:{app.config.port}", flush=True)
    print(f"{app.layout['pixelCount']} pixels / {app.channel_count} RGB channels; "
          f"DDP {app.config.ddp_port}; sACN {app.config.sacn_port}, "
          f"universes {app.config.start_universe}-{app.config.start_universe + app.sacn.universe_count - 1} "
          f"({app.config.universe_size} slots)", flush=True)
    print(f"Unreal relay: {app.config.relay_host}:{app.config.relay_port} "
          f"({'enabled' if app.config.relay_enabled else 'disabled'}). Ctrl+C stops the server.", flush=True)
    for protocol, state in app.receivers.items():
        if state["error"]:
            print(f"{protocol}: {state['error']}", file=sys.stderr, flush=True)
    try:
        while True:
            time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
