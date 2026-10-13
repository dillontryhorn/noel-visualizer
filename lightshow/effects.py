"""Deterministic, spatial RGB demo effects with no external dependencies."""

import colorsys
import math

EFFECTS = ("aurora", "candy", "rainbow", "sparkle", "solid", "blackout")


def render(effect, time_value, mapping, channel_count, bpm=120, solid_color="#ffcc88"):
    rgb = bytearray(channel_count)
    if effect == "blackout":
        return rgb
    beat = time_value * bpm / 60
    pulse = .72 + .28 * math.exp(-((beat % 1) / .16) ** 2)
    solid = tuple(int(solid_color[index:index + 2], 16) for index in (1, 3, 5))
    for offset, (x, y, z), fixture_id, local in mapping:
        if effect == "solid":
            color = solid
        elif effect == "candy":
            stripe = int((y * 1.7 + x * .8 + local * .06 - time_value * 1.4) % 3)
            palette = ((255, 32, 52), (32, 225, 145), (255, 225, 195))
            color = tuple(int(value * pulse) for value in palette[stripe])
        elif effect == "rainbow":
            hue = (x * .04 + y * .08 + z * .02 + time_value * .09) % 1
            color = tuple(int(value * 255 * pulse) for value in colorsys.hsv_to_rgb(hue, .85, 1))
        elif effect == "sparkle":
            # Deterministic smooth flashes mean paused frames and scrub are stable.
            seed = offset * 12.9898 + x * 78.233 + z * 7.3
            phase = (math.sin(seed) * 43758.5453) % 1
            flare = max(0., math.cos(time_value * (1.3 + phase * 2.4) + phase * math.tau)) ** 28
            color = (int(35 + 220 * flare), int(18 + 220 * flare), int(6 + 205 * flare))
        else:
            curtain = .5 + .5 * math.sin(x * .7 + time_value * .9 + math.sin(y * .65 - time_value * .4))
            hue = .44 + .31 * curtain + .045 * math.sin(z + time_value * .3)
            value = (.2 + .8 * (.5 + .5 * math.sin(y * .8 - time_value * 1.6 + x * .2))) * pulse
            color = tuple(int(value_rgb * 255) for value_rgb in colorsys.hsv_to_rgb(hue % 1, .85, value))
        rgb[offset:offset + 3] = bytes(color)
    return rgb
