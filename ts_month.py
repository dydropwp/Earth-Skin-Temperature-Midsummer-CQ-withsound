# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib"]
# ///
"""
A whole month of Earth skin temperature, twice: thirty-one days drawn on top
of each other, and the same thirty-one days as a grid of colour, one square
per hour.

Run it:
    uv run ts_month.py

Writes out/ts-month.png and opens a window.
"""

import csv
import datetime as dt
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# ---------------------------------------------------------------------------
# The knobs.
# ---------------------------------------------------------------------------

PAPER = "#faf8f4"
INK = "#1d1d1b"
LINE = "#2a6f7f"           # every ordinary day
HOT = "#d6591d"            # the one day drawn thick
LINE_ALPHA = 0.28          # how faint each of the thirty-one days is
FIGSIZE = (13, 5)

# light green -> yellow -> orange -> red -> dark red, smooth
TEMPS = LinearSegmentedColormap.from_list("ts-scale", [
    "#e8f5e9",   # 0.00  very light green
    "#c5e1a5",   # 0.10  light green
    "#aed581",   # 0.20  green
    "#dce775",   # 0.30  yellow-green
    "#fff176",   # 0.40  pale yellow
    "#ffd54f",   # 0.50  yellow
    "#ffb74d",   # 0.60  amber
    "#ff8a65",   # 0.70  light orange
    "#ef5350",   # 0.80  red
    "#c62828",   # 0.90  deep red
    "#8e0000",   # 1.00  dark red
])

HERE = Path(__file__).parent
DATA = HERE / "data" / "ts-chongqing-2026-08.csv"
OUT = HERE / "out"

# ---------------------------------------------------------------------------
# Reading and reshaping.
# ---------------------------------------------------------------------------


def load_month():
    """Read the CSV into (datetime, temperature) pairs."""
    rows = []
    with DATA.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            when = dt.datetime.strptime(record["time"], "%Y-%m-%d %H:%M")
            rows.append((when, float(record["ts"])))
    return rows


def group_by_day(rows):
    """Turn the flat list into one (date, [24 temperatures]) per day."""
    buckets = {}
    for when, value in rows:
        buckets.setdefault(when.date(), [None] * 24)[when.hour] = value
    return [(day, buckets[day]) for day in sorted(buckets)]


# ---------------------------------------------------------------------------
# The drawing.
# ---------------------------------------------------------------------------


def main():
    days = group_by_day(load_month())
    if not days:
        raise SystemExit(f"no data in {DATA}")

    hours = list(range(24))
    month_name = days[0][0].strftime("%B %Y")

    # the hottest day gets the thick line
    pick = max(days, key=lambda pair: max(pair[1]))

    figure, (left, right) = plt.subplots(1, 2, figsize=FIGSIZE, facecolor=PAPER)

    # -- left: thirty-one lines, one per day --------------------------------
    left.set_facecolor(PAPER)
    for when, temps in days:
        left.plot(hours, temps, color=LINE, alpha=LINE_ALPHA, linewidth=1.0)
    left.plot(hours, pick[1], color=HOT, linewidth=2.6,
              label=f"{pick[0]:%d %b} (hottest)")
    left.set_title(f"{month_name} — every day, drawn over the last",
                   color=INK, fontsize=12)
    left.set_xlabel("hour of the day (LST)", color=INK)
    left.set_ylabel("Earth skin temperature (°C)", color=INK)
    left.set_xticks([0, 6, 12, 18, 23])
    left.tick_params(colors=INK)
    left.grid(color=INK, alpha=0.1)
    left.legend(frameon=False, labelcolor=INK)
    for side in ("top", "right"):
        left.spines[side].set_visible(False)

    # -- right: the same numbers as a grid of colour ------------------------
    grid = [temps for when, temps in days]

    # stretch the colour band a bit past the data so the dawn jump is softer
    flat = [t for row in grid for t in row]
    vmin, vmax = min(flat), max(flat)
    pad = (vmax - vmin) * 0.15

    picture = right.imshow(grid, aspect="auto", cmap=TEMPS, origin="upper",
                           vmin=vmin - pad, vmax=vmax + pad,
                           extent=(-0.5, 23.5, len(days) + 0.5, 0.5))
    right.set_title("the same numbers as colour — one square per hour",
                    color=INK, fontsize=12)
    right.set_xlabel("hour of the day (LST)", color=INK)
    right.set_ylabel("day of the month", color=INK)
    right.set_xticks([0, 6, 12, 18, 23])
    right.set_yticks([1, 5, 10, 15, 20, 25, 31])
    right.tick_params(colors=INK)
    bar = figure.colorbar(picture, ax=right)
    bar.set_label("Earth skin temperature (°C)", color=INK)
    bar.ax.tick_params(colors=INK)

    OUT.mkdir(exist_ok=True)
    target = OUT / "ts-month.png"
    figure.tight_layout()
    figure.savefig(target, dpi=150, facecolor=PAPER)
    print(f"wrote {target.relative_to(HERE)} — {len(days)} days, {len(days) * 24} numbers")
    plt.show()


if __name__ == "__main__":
    main()