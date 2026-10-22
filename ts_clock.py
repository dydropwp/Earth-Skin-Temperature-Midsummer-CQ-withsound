# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "numpy", "imageio-ffmpeg"]
# ///

"""
The hottest day of the month, bent into a circle: hour becomes an angle, °C a
radius. A hand sweeps from midnight while a sine tone follows the temperature.

Outputs:
    out/ts-clock-hottest.png   the full 24-hour shape, still
    out/ts-clock-hottest.mp4  a 24-second clock video with synced audio

Run it:
    uv run ts_clock.py
"""

from array import array
import csv
import datetime as dt
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

import imageio_ffmpeg
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
import numpy as np

# ---------------------------------------------------------------------------
# The knobs.
# ---------------------------------------------------------------------------

BASELINE = 22.0            # °C, subtracted from every temperature
HOURS = 24
TURN = 360                 # degrees in a full turn
FPS = 12                   # 12 frames per hour makes a 24-second video
DOTS = True
LINE_WIDTH = 2.4
PAD = 0.20
DPI = 96
SAMPLE_RATE = 22050
MIN_FREQUENCY = 220.0
MAX_FREQUENCY = 440.0
AMPLITUDE = 0.25

PAPER = "#faf8f4"
INK = "#1d1d1b"
MARK = "#d6591d"           # moving dot, hand, and the trailing edge

# green -> yellow -> orange -> red -> dark red
COLOURS = LinearSegmentedColormap.from_list("ts-scale", [
    "#e8f5e9", "#c5e1a5", "#aed581", "#dce775",
    "#fff176", "#ffd54f", "#ffb74d", "#ff8a65",
    "#ef5350", "#c62828", "#8e0000",
])

HERE = Path(__file__).parent
DATA = HERE / "data" / "ts-chongqing-2026-08.csv"
OUT = HERE / "out"
PNG = OUT / "ts-clock-hottest.png"
VIDEO = OUT / "ts-clock-hottest.mp4"

# ---------------------------------------------------------------------------
# Reading.
# ---------------------------------------------------------------------------


def load_month():
    rows = []
    with DATA.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            when = dt.datetime.strptime(record["time"], "%Y-%m-%d %H:%M")
            rows.append((when, float(record["ts"])))
    return rows


def group_by_day(rows):
    buckets = {}
    for when, value in rows:
        buckets.setdefault(when.date(), [None] * 24)[when.hour] = value
    return [(day, buckets[day]) for day in sorted(buckets)]


def hottest_day(days):
    return max(days, key=lambda pair: max(pair[1]))


# ---------------------------------------------------------------------------
# The transformation.
# ---------------------------------------------------------------------------


def to_xy(hour, radius):
    """Polar to cartesian. Hour 0 at the top, clockwise. Accepts float hours."""
    angle = math.radians(90 - hour / HOURS * TURN)
    return (radius * math.cos(angle), radius * math.sin(angle))


def temperature_frequency(temperature, day_min, day_max):
    """Map a day's temperature range to one octave, from 220 to 440 Hz."""
    if day_max == day_min:
        return (MIN_FREQUENCY + MAX_FREQUENCY) / 2
    fraction = (temperature - day_min) / (day_max - day_min)
    return MIN_FREQUENCY + fraction * (MAX_FREQUENCY - MIN_FREQUENCY)


# ---------------------------------------------------------------------------
# Background, drawn identically every frame.
# ---------------------------------------------------------------------------


def draw_background(axes, radii):
    lo, hi = min(radii), max(radii)
    mean = sum(radii) / len(radii)

    for hour in range(HOURS):
        inner = to_xy(hour, lo * 0.45)
        outer = to_xy(hour, hi * 1.06)
        axes.plot([inner[0], outer[0]], [inner[1], outer[1]],
                  color=INK, alpha=0.32 if hour % 6 == 0 else 0.10,
                  linewidth=0.9)
        if hour % 6 == 0:
            label = to_xy(hour, hi * 1.30)
            axes.text(label[0], label[1], f"{hour:02d}:00",
                      color=INK, alpha=0.7, fontsize=9,
                      ha="center", va="center")

    ring = [to_xy(hour, mean) for hour in range(HOURS + 1)]
    axes.plot([p[0] for p in ring], [p[1] for p in ring],
              color=INK, alpha=0.22, linewidth=0.9, linestyle="--")


# ---------------------------------------------------------------------------
# The still: whole 24-hour shape.
# ---------------------------------------------------------------------------


def draw_still(axes, temps, colour):
    radii = [t - BASELINE for t in temps]
    draw_background(axes, radii)

    points = [to_xy(h, radii[h]) for h in range(HOURS)]
    points.append(points[0])
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    axes.fill(xs, ys, color=colour, alpha=0.16)
    axes.plot(xs, ys, color=colour, linewidth=LINE_WIDTH)
    if DOTS:
        axes.plot(xs, ys, "o", color=colour, markersize=4)

    hot = radii.index(max(radii))
    top = to_xy(hot, max(radii))
    axes.plot(top[0], top[1], "o", color=INK, markersize=8, zorder=5)


# ---------------------------------------------------------------------------
# The sweep: trail grows from 00:00 to the moving tip, a hand ties tip to centre.
# ---------------------------------------------------------------------------


def draw_sweep(axes, temps, colour, t_now):
    """t_now is a continuous hour value in [0, 24)."""
    radii = [t - BASELINE for t in temps]
    draw_background(axes, radii)

    # the trail so far: one vertex per completed hour, plus a fractional tip
    full = int(t_now)
    trail = [to_xy(h, radii[h]) for h in range(full + 1)]

    h1 = full % HOURS
    h2 = (h1 + 1) % HOURS
    frac = t_now - full
    r_tip = radii[h1] + (radii[h2] - radii[h1]) * frac
    tip = to_xy(t_now, r_tip)
    trail.append(tip)

    xs = [p[0] for p in trail]
    ys = [p[1] for p in trail]
    axes.plot(xs, ys, color=colour, linewidth=LINE_WIDTH, zorder=3)

    # the hand: a straight line from the centre to the moving tip
    axes.plot([0, tip[0]], [0, tip[1]], color=MARK, linewidth=1.8,
              alpha=0.9, zorder=4)

    # a small hub at the centre
    axes.plot(0, 0, "o", color=INK, markersize=3.5, zorder=5)

    # the moving dot
    axes.plot(tip[0], tip[1], "o", color=MARK, markersize=11,
              zorder=5, markeredgecolor=PAPER, markeredgewidth=1.5)


def write_audio(path, temps):
    """Write 24 seconds of continuous sine tone, one data hour per second."""
    day_min, day_max = min(temps), max(temps)
    samples = array("h")
    phase = 0.0
    phase_step = 2 * math.pi / SAMPLE_RATE

    for hour, start_temp in enumerate(temps):
        end_temp = temps[(hour + 1) % HOURS]
        start_frequency = temperature_frequency(start_temp, day_min, day_max)
        end_frequency = temperature_frequency(end_temp, day_min, day_max)
        for sample_index in range(SAMPLE_RATE):
            fraction = sample_index / SAMPLE_RATE
            frequency = start_frequency + (end_frequency - start_frequency) * fraction
            time_seconds = hour + fraction
            envelope = min(1.0, time_seconds / 0.15, (HOURS - time_seconds) / 0.15)
            value = int(32767 * AMPLITUDE * max(0.0, envelope) * math.sin(phase))
            samples.append(value)
            phase += frequency * phase_step

    if sys.byteorder != "little":
        samples.byteswap()

    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(samples.tobytes())


def write_video(temps, colour, title, limit):
    """Render the clock sweep and mux its temperature tone into an MP4."""
    width = height = round(5.5 * DPI)
    temporary_video = VIDEO.with_name(f"{VIDEO.stem}.tmp{VIDEO.suffix}")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}", "-r", str(FPS), "-i", "-",
        "-i", None,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-shortest", str(temporary_video),
    ]

    with tempfile.TemporaryDirectory(dir=OUT) as temporary_directory:
        audio_path = Path(temporary_directory) / "temperature.wav"
        write_audio(audio_path, temps)
        command[command.index(None)] = str(audio_path)

        figure, axes = plt.subplots(figsize=(5.5, 5.5), dpi=DPI,
                                    facecolor=PAPER)
        figure.subplots_adjust(left=0.06, right=0.94, top=0.86, bottom=0.06)
        process = None
        try:
            process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            for frame in range(HOURS * FPS):
                axes.clear()
                axes.set_facecolor(PAPER)
                axes.set_aspect("equal")
                axes.axis("off")
                axes.set_xlim(-limit, limit)
                axes.set_ylim(-limit, limit)
                axes.set_title(title, color=INK, fontsize=11, pad=16)
                draw_sweep(axes, temps, colour, frame / FPS)

                image, (frame_width, frame_height) = figure.canvas.print_to_buffer()
                rgba = np.frombuffer(image, dtype=np.uint8).reshape(
                    frame_height, frame_width, 4
                )
                rgb = np.ascontiguousarray(rgba[:, :, :3])
                process.stdin.write(rgb.tobytes())

            process.stdin.close()
            error_output = process.stderr.read()
            return_code = process.wait()
            if return_code:
                raise RuntimeError(
                    f"FFmpeg could not create the video: "
                    f"{error_output.decode(errors='replace').strip()}"
                )
            os.replace(temporary_video, VIDEO)
        except Exception:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            temporary_video.unlink(missing_ok=True)
            raise
        finally:
            plt.close(figure)


# ---------------------------------------------------------------------------
# The outputs.
# ---------------------------------------------------------------------------


def main():
    days = group_by_day(load_month())
    if not days:
        raise SystemExit(f"no data in {DATA}")

    day, temps = hottest_day(days)

    all_temps = [t for _, row in days for t in row]
    norm = Normalize(vmin=min(all_temps), vmax=max(all_temps))
    colour = COLOURS(norm(max(temps)))

    rad_max = max(temps) - BASELINE
    lim = rad_max * (1 + PAD) * 1.15

    title = (f"Chongqing — {day:%d %B %Y} (hottest day)\n"
             f"hour as angle, °C as radius (baseline {BASELINE:.0f} °C)")

    OUT.mkdir(exist_ok=True)

    # -- 1. the still --------------------------------------------------------
    figure, axes = plt.subplots(figsize=(5.5, 5.5), facecolor=PAPER)
    figure.subplots_adjust(left=0.06, right=0.94, top=0.86, bottom=0.06)
    axes.set_facecolor(PAPER)
    axes.set_aspect("equal")
    axes.axis("off")
    axes.set_xlim(-lim, lim)
    axes.set_ylim(-lim, lim)
    draw_still(axes, temps, colour)
    axes.set_title(title, color=INK, fontsize=11, pad=16)
    figure.savefig(PNG, dpi=150, facecolor=PAPER)
    print(f"wrote {PNG.relative_to(HERE)}")
    plt.close(figure)

    # -- 2. the clock video with its temperature tone ------------------------
    write_video(temps, colour, title, lim)
    print(f"wrote {VIDEO.relative_to(HERE)} — 24 seconds at {FPS} fps with audio")
    print(f"\nhottest day: {day:%Y-%m-%d}, "
          f"peak {max(temps):.2f} °C at {temps.index(max(temps)):02d}:00 LST")


if __name__ == "__main__":
    main()