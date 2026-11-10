# RGB effects: the colours of one frame for a number of LEDs
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Ported from OpenLinkHub by Nikola Jurkovic (src/rgb/*.go): rgb.go and the
# effects rainbow, pastelrainbow, watercolor, gradient, temperature,
# colorpulse, rotator, wave, storm, flickering, colorshift and colorwarp.
# Only the plain output (one R, G, B per LED) is ported, not the AIO, LCD,
# inverted and buffer variants. Profiles use OpenLinkHub's JSON format
# ("speed", "brightness", "start", "middle", "end", "gradients").

import math
import random
import time

# Defaults from OpenLinkHub's database/rgb.json, for the modes a headset has.
# Colours: (red, green, blue, brightness, temperature)
_DEFAULTS = {
    "colorpulse": (1, (255, 0, 0, 1, 0), None, (0, 0, 0, 1, 0)),
    "colorshift": (4, (255, 0, 0, 1, 0), None, (255, 100, 0, 1, 0)),
    "colorwarp": (1, None, None, None),
    "cpu-temperature": (4, (0, 255, 0, 1, 20), (255, 255, 0, 1, 50), (255, 0, 0, 1, 95)),
    "flickering": (1, (255, 0, 0, 1, 0), None, (255, 100, 0, 1, 0)),
    "gpu-temperature": (4, (0, 255, 0, 1, 20), (255, 255, 0, 1, 50), (255, 0, 0, 1, 80)),
    "gradient": (10, None, None, None),
    "rainbow": (4, None, None, None),
    "pastelrainbow": (4, None, None, None),
    "rotator": (5, (255, 100, 149, 1, 0), None, (255, 100, 152, 1, 0)),
    "static": (4, (0, 255, 255, 0.5, 0), None, (0, 255, 255, 0.5, 0)),
    "storm": (4, (32, 62, 77, 0.5, 0), None, (255, 255, 255, 0.5, 0)),
    "watercolor": (8, None, None, None),
    "wave": (5, (65, 143, 232, 1, 0), None, (130, 130, 130, 1, 0)),
}
_GRADIENT = [(255, 0, 0, 0), (0, 255, 0, 0.33), (0, 0, 255, 0.66), (255, 255, 0, 1)]


def _color_json(values):
    if values is None:
        return {"red": 0, "green": 0, "blue": 0, "brightness": 0, "position": 0, "temperature": 0, "Hex": ""}
    r, g, b, brightness, temperature = values
    return {"red": r, "green": g, "blue": b, "brightness": brightness, "position": 0,
            "temperature": temperature, "Hex": ""}


def default_profiles():
    profiles = {}
    for mode, (speed, start, middle, end) in _DEFAULTS.items():
        profiles[mode] = {"speed": speed, "brightness": 1, "smoothness": 0, "start": _color_json(start),
                          "middle": _color_json(middle), "end": _color_json(end), "gradients": None,
                          "minTemp": 0, "maxTemp": 0}
    profiles["gradient"]["gradients"] = {
        str(i): {"red": r, "green": g, "blue": b, "brightness": 1, "position": p, "temperature": 0, "Hex": ""}
        for i, (r, g, b, p) in enumerate(_GRADIENT)}
    return profiles


class Color:
    __slots__ = ("red", "green", "blue", "brightness", "position", "temperature")

    def __init__(self, red=0.0, green=0.0, blue=0.0, brightness=0.0, position=0.0, temperature=0.0):
        self.red, self.green, self.blue = float(red), float(green), float(blue)
        self.brightness, self.position, self.temperature = float(brightness), float(position), float(temperature)

    @classmethod
    def from_json(cls, data):
        data = data or {}
        return cls(*(float(data.get(k) or 0) for k in ("red", "green", "blue", "brightness", "position",
                                                       "temperature")))

    def is_zero(self):
        return not any((self.red, self.green, self.blue, self.brightness, self.position, self.temperature))

    def copy(self):
        return Color(self.red, self.green, self.blue, self.brightness, self.position, self.temperature)


def byte(value):
    """Go's byte(float64) for the values that occur: truncate, kept within 0-255."""
    return max(0, min(255, int(value)))


def modify_brightness(c):
    bts = max(0.0, min(1.0, c.brightness))
    return Color(byte(c.red * bts), byte(c.green * bts), byte(c.blue * bts))


def lerp(a, b, t):
    return a + t * (b - a)


def interpolate_color(c1, c2, t, bts):
    return modify_brightness(Color(lerp(c1.red, c2.red, t), lerp(c1.green, c2.green, t),
                                   lerp(c1.blue, c2.blue, t), bts))


def interpolate_colors(c1, c2, t, bts):
    mix = [byte(a * (1 - t) + b * t) for a, b in ((c1.red, c2.red), (c1.green, c2.green), (c1.blue, c2.blue))]
    return modify_brightness(Color(*mix, bts))


def interpolate_colors_with_brightness(c1, c2, t):
    bts = c1.brightness * (1 - t) + c2.brightness * t
    mix = [a * c1.brightness * (1 - t) + b * c2.brightness * t
           for a, b in ((c1.red, c2.red), (c1.green, c2.green), (c1.blue, c2.blue))]
    return modify_brightness(Color(*mix, bts))


def random_color(bts):
    return modify_brightness(Color(random.randrange(256), random.randrange(256), random.randrange(256), bts))


def _interpolate(r1, g1, b1, r2, g2, b2, fraction):
    return (int((r1 + fraction * (r2 - r1)) * 255), int((g1 + fraction * (g2 - g1)) * 255),
            int((b1 + fraction * (b2 - b1)) * 255))


def rainbow_color(position):
    position = math.fmod(position, 1.0)
    if position < 0.2:
        return _interpolate(1, 0, 0, 1, 1, 0, position / 0.2)
    if position < 0.4:
        return _interpolate(1, 1, 0, 0, 1, 0, (position - 0.2) / 0.2)
    if position < 0.6:
        return _interpolate(0, 1, 0, 0, 1, 1, (position - 0.4) / 0.2)
    if position < 0.8:
        return _interpolate(0, 1, 1, 0, 0, 1, (position - 0.6) / 0.2)
    return _interpolate(0, 0, 1, 1, 0, 0, (position - 0.8) / 0.2)


PASTEL = ((244, 253, 255), (255, 218, 247), (255, 140, 230), (254, 96, 219), (255, 17, 206), (254, 28, 206),
          (255, 106, 225), (255, 184, 241), (255, 230, 248), (255, 255, 203), (255, 255, 155), (255, 255, 80),
          (255, 255, 33), (216, 250, 52), (161, 244, 119), (105, 237, 185), (14, 208, 250), (37, 210, 255),
          (114, 227, 255), (159, 235, 253))


def pastel_color(position):
    position -= math.floor(position)
    pos = position * len(PASTEL)
    index = int(pos)
    frac = pos - index
    c1, c2 = PASTEL[index], PASTEL[(index + 1) % len(PASTEL)]
    return tuple(int(a + (b - a) * frac) for a, b in zip(c1, c2))


def hsb_to_rgb(h, s, v):
    h = math.fmod(h, 360)
    c = v * s
    x = c * (1 - abs(math.fmod(h / 60.0, 2) - 1))
    m = v - c
    r, g, b = {0: (c, x, 0), 1: (x, c, 0), 2: (0, c, x), 3: (0, x, c), 4: (x, 0, c)}.get(int(h // 60), (c, 0, x))
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


def hsv_to_rgb(hue, saturation, value):
    """HsvToRgb of rotator.go, packed as 0xRRGGBB (its quirks included)."""
    h = hue % 360
    s = saturation / 255.0
    v = value / 255.0
    c = v * s
    x = c * (1 - abs(h / 60.0 - float((h // 60) * 2)))
    m = v - c
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return ((int((r + m) * 255) << 16) | (int((g + m) * 255) << 8) | int((b + m) * 255)) & 0xFFFFFFFF


def _map_temperature(temp, low, high):
    if high == low:
        return 0.5
    clamped = max(min(low, high), min(max(low, high), temp))
    return (clamped - low) / (high - low)


def temperature_color(start, middle, end, temp, bts):
    c1, c2, c3 = start, middle, end
    if c1.temperature > c2.temperature:
        c1, c2 = c2, c1
    if c2.temperature > c3.temperature:
        c2, c3 = c3, c2
    if c1.temperature > c2.temperature:
        c1, c2 = c2, c1
    if temp <= c1.temperature:
        return interpolate_color(c1, c1, 0, bts)
    if temp <= c2.temperature:
        return interpolate_color(c1, c2, _map_temperature(temp, c1.temperature, c2.temperature), bts)
    if temp <= c3.temperature:
        return interpolate_color(c2, c3, _map_temperature(temp, c2.temperature, c3.temperature), bts)
    return interpolate_color(c3, c3, 0, bts)


def gradient_color(elapsed, gradients, duration):
    if duration <= 0:
        duration = 5
    progress = math.fmod(elapsed / duration, 1.0)
    colors = sorted((Color.from_json(gradients[k]) for k in sorted(gradients, key=int)), key=lambda c: c.position)
    if len(colors) < 2:
        return None
    a, b, segment = Color(), Color(), 0.0
    for i in range(len(colors) - 1):
        if colors[i].position <= progress < colors[i + 1].position:
            a, b = colors[i], colors[i + 1]
            segment = (progress - a.position) / (b.position - a.position)
            break
    if progress >= colors[-1].position:
        a, b = colors[-1], colors[0]
        span = 1.0 - a.position + b.position
        segment = (progress - a.position) / span if span else 0.0
    return interpolate_colors_with_brightness(a, b, segment)


class Animation:
    """One running effect (OpenLinkHub's activeRgb): start time, random colours, colorshift/colorwarp state."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.start = clock()
        self.random_start = random_color(1)
        self.random_end = random_color(1)
        self.warp_start = None
        self.warp_end = None
        self.warp_cycle = 0

    def frame(self, mode, profile, channels, brightness, cpu_temp=0.0, gpu_temp=0.0):
        """R, G, B per LED (bytes of channels * 3); brightness 0-1 from the slider."""
        if mode == "off" or profile is None:
            return bytes(channels * 3)
        speed = max(0.1, min(10.0, float(profile.get("speed") or 0)))
        start, end = Color.from_json(profile.get("start")), Color.from_json(profile.get("end"))
        middle = Color.from_json(profile.get("middle"))
        if start.is_zero() or end.is_zero():
            start, end, middle = self.random_start.copy(), self.random_end.copy(), Color()
        for c in (start, end, middle):
            c.brightness = brightness
        seconds = self.clock() - self.start
        ms = int(seconds * 1000)
        out = []

        def same(color):
            out.extend([byte(color.red), byte(color.green), byte(color.blue)] * channels)

        if mode in ("rainbow", "pastelrainbow"):
            factor = 4.0 / speed
            pick = rainbow_color if mode == "rainbow" else pastel_color
            for i in range(channels):
                r, g, b = pick(math.fmod(i / channels + seconds * factor / 4.0, 1.0))
                c = modify_brightness(Color(r, g, b, brightness))
                out += [byte(c.red), byte(c.green), byte(c.blue)]
        elif mode == "watercolor":
            elapsed = seconds / speed
            for i in range(channels):
                position = math.fmod(math.fmod(i / channels + elapsed * 4.0, 1.0), 1.0)
                r, g, b = hsb_to_rgb(position * 360, 0.4, 1.0)
                c = modify_brightness(Color(r, g, b, brightness))
                out += [byte(c.red), byte(c.green), byte(c.blue)]
        elif mode == "gradient":
            color = gradient_color(seconds, profile.get("gradients") or {}, float(profile.get("speed") or 0))
            if color is None:
                return bytes(channels * 3)
            same(color)
        elif mode in ("cpu-temperature", "gpu-temperature"):
            temp = cpu_temp if mode == "cpu-temperature" else gpu_temp
            same(temperature_color(start, middle, end, float(temp or 0), brightness))
        elif mode == "colorpulse":
            same(interpolate_colors(start, end, math.fmod(ms / (speed * 1000), 1.0), brightness))
        elif mode == "static":
            same(modify_brightness(start))
        elif mode == "rotator":
            hue = ms / speed / 2
            for j in range(channels):
                parts = [hsv_to_rgb(int(hue) + j * 5, 255, int(v)) & 0xFF for v in (start.red, start.green, start.blue)]
                c = modify_brightness(Color(*parts, brightness))
                out += [byte(c.red), byte(c.green), byte(c.blue)]
        elif mode == "wave":
            progress = ms / (speed * 100)
            for i in range(channels):
                intensity = 0.5 * (1 + math.sin(2 * math.pi * (progress + i) / speed))
                c = interpolate_color(start, end, intensity, brightness)
                out += [byte(c.red * intensity), byte(c.green * intensity), byte(c.blue * intensity)]
        elif mode == "storm":
            for _ in range(channels):
                c = end if random.random() < 0.001 else start
                c = modify_brightness(Color(c.red, c.green, c.blue, start.brightness))
                out += [byte(c.red), byte(c.green), byte(c.blue)]
        elif mode == "flickering":
            limit = max(1, channels * int(speed))
            for j in range(channels):
                c = interpolate_colors(start, end, j / channels, brightness)
                out += [0, 0, 0] if random.randrange(limit) == 1 else [byte(c.red), byte(c.green), byte(c.blue)]
        elif mode == "colorshift":
            total = ms / (speed * 1000)
            progress = math.fmod(total, 1.0)
            a, b = (start, end) if int(total) % 2 == 0 else (end, start)
            same(interpolate_color(a, b, progress, brightness))
        elif mode == "colorwarp":
            total = ms / (speed * 1000)
            cycle = int(total)
            if self.warp_start is None:
                self.warp_start = random_color(brightness)
            if self.warp_end is None:
                self.warp_end = random_color(brightness)
            if cycle != self.warp_cycle:
                self.warp_cycle = cycle
                self.warp_start, self.warp_end = self.warp_end, random_color(brightness)
            same(interpolate_color(self.warp_start, self.warp_end, math.fmod(total, 1.0), brightness))
        else:
            return bytes(channels * 3)
        return bytes(out)
