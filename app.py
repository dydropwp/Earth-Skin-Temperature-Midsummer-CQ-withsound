# /// script
# requires-python = ">=3.10"
# dependencies = ["streamlit", "matplotlib"]
# ///
"""
Pick a day, see it bent into a clock: hour as angle, °C as radius.

The temperature rings and the canvas are fixed to the whole month's range,
so a cool day and a hot day can be compared directly: the ring labelled 32°
sits in the same place on every day. The dashed daily-mean ring is the only
background element that moves with the selected day.

Run it:
    uv run --with streamlit --with matplotlib streamlit run app.py
"""

import csv
import datetime as dt
import math
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st
from matplotlib.colors import LinearSegmentedColormap, Normalize

BASELINE = 20.0            # °C — below the month's minimum, so radii stay positive
RADIUS_SCALE = 1.0
HOURS = 24
TURN = 360
LINE_WIDTH = 2.4
DOTS = True
PAD = 0.20

PAPER = "#faf8f4"
INK = "#1d1d1b"

COLOURS = LinearSegmentedColormap.from_list("ts-scale", [
    "#e8f5e9", "#c5e1a5", "#aed581", "#dce775",
    "#fff176", "#ffd54f", "#ffb74d", "#ff8a65",
    "#ef5350", "#c62828", "#8e0000",
])

HERE = Path(__file__).parent
DATA = HERE / "data" / "ts-chongqing-2026-08.csv"


def load_month(path):
    rows = []
    with open(path, encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            when = dt.datetime.strptime(record["time"], "%Y-%m-%d %H:%M")
            rows.append((when, float(record["ts"])))
    return rows


def group_by_day(rows):
    buckets = {}
    for when, value in rows:
        buckets.setdefault(when.date(), [None] * 24)[when.hour] = value
    return [(day, buckets[day]) for day in sorted(buckets)]


def to_xy(hour, radius):
    angle = math.radians(90 - hour / HOURS * TURN)
    return (radius * math.cos(angle), radius * math.sin(angle))


def draw_background(axes, radii, rad_max, month_max):
    mean = sum(radii) / len(radii)

    # hour spokes span the fixed canvas
    for hour in range(HOURS):
        inner = to_xy(hour, rad_max * 0.06)
        outer = to_xy(hour, rad_max * 1.02)
        axes.plot([inner[0], outer[0]], [inner[1], outer[1]],
                  color=INK, alpha=0.32 if hour % 6 == 0 else 0.10,
                  linewidth=0.9)
        if hour % 6 == 0:
            label = to_xy(hour, rad_max * 1.14)
            axes.text(label[0], label[1], f"{hour:02d}:00",
                      color=INK, alpha=0.7, fontsize=9,
                      ha="center", va="center")

    # fixed temperature rings, positioned on the month's scale
    for label_temp in range(int(BASELINE) + 4, int(month_max) + 1, 4):
        r = (label_temp - BASELINE) * RADIUS_SCALE
        if r <= 0 or r > rad_max * 1.02:
            continue
        ring = [to_xy(hour, r) for hour in range(HOURS + 1)]
        axes.plot([p[0] for p in ring], [p[1] for p in ring],
                  color=INK, alpha=0.12, linewidth=0.7)
        spot = to_xy(0, r)
        axes.text(spot[0], spot[1], f"{label_temp}°",
                  color=INK, alpha=0.45, fontsize=7,
                  ha="center", va="center")

    # the daily mean ring, dashed — the only moving background element
    ring = [to_xy(hour, mean) for hour in range(HOURS + 1)]
    axes.plot([p[0] for p in ring], [p[1] for p in ring],
              color=INK, alpha=0.25, linewidth=0.9, linestyle="--")


def draw_shape(axes, temps, colour, rad_max, month_max):
    radii = [(t - BASELINE) * RADIUS_SCALE for t in temps]
    draw_background(axes, radii, rad_max, month_max)

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


st.title("Chongqing skin temperature")
st.caption(
    f"August 2026. Hour as angle, °C as radius. The centre of the clock is "
    f"{BASELINE:.0f} °C. The temperature rings and the canvas are fixed to "
    f"the whole month, so the same ring sits in the same place on every "
    f"day — a small shape really is a cool day. Coldest just before sunrise, "
    f"warmest in the early afternoon. Dashed ring = daily mean; black dot = "
    f"hottest hour."
)

if not DATA.exists():
    st.error(f"data file not found: {DATA}")
    st.stop()

days = group_by_day(load_month(str(DATA)))
if not days:
    st.error("no rows to plot")
    st.stop()

# whole-month ranges, computed once, used for the fixed canvas and rings
ALL_TEMPS = [t for _, row in days for t in row]
MONTH_MAX = max(ALL_TEMPS)
MONTH_MIN = min(ALL_TEMPS)
RAD_MAX = (MONTH_MAX - BASELINE) * RADIUS_SCALE
LIM = RAD_MAX * (1 + PAD) * 1.15

labels = [day.strftime("%d %B") for day, _ in days]
choice = st.selectbox("Pick a day", labels, index=0)
day, temps = days[labels.index(choice)]

norm = Normalize(vmin=MONTH_MIN, vmax=MONTH_MAX)
colour = COLOURS(norm(max(temps)))

figure, axes = plt.subplots(figsize=(6, 6), facecolor=PAPER)
figure.subplots_adjust(left=0.05, right=0.95, top=0.90, bottom=0.05)
axes.set_facecolor(PAPER)
axes.set_aspect("equal")
axes.axis("off")
axes.set_xlim(-LIM, LIM)
axes.set_ylim(-LIM, LIM)

draw_shape(axes, temps, colour, RAD_MAX, MONTH_MAX)
axes.set_title(
    f"{day:%d %B %Y}\n"
    f"hour as angle, °C as radius (centre = {BASELINE:.0f} °C)",
    color=INK, fontsize=11, pad=16,
)

st.pyplot(figure)
plt.close(figure)

peak = max(temps)
trough = min(temps)
mean = sum(temps) / len(temps)
st.markdown(
    f"**{day:%d %B %Y}** — peak **{peak:.2f} °C** at "
    f"{temps.index(peak):02d}:00, lowest **{trough:.2f} °C** at "
    f"{temps.index(trough):02d}:00, mean **{mean:.2f} °C**, "
    f"range **{peak - trough:.2f} °C**."
)