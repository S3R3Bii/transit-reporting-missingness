"""Original figures with numeric evidence read back from actual plot artists."""

import csv
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    with (ROOT / "results" / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def luminance(color):
    rgb = to_rgb(color)
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return sum(a * b for a, b in zip(linear, [0.2126, 0.7152, 0.0722]))


def main():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
            "svg.hashsalt": "transit07-fixed",
        }
    )
    dest = ROOT / "figures"
    dest.mkdir(exist_ok=True)
    points = read("held-points.csv")
    settings = read("held-setting-summary.csv")
    intervals = read("held-bound-summary.csv")
    values = {"growth": {}, "errors": {}, "bounds": {}, "annotations": []}
    names = {
        "truth": "Complete published cohort",
        "zero_fill": "Zero fill",
        "count_rescaled": "Count rescaling",
        "matched_panel": "Matched panel",
    }
    colors = {
        "truth": "#16546c",
        "zero_fill": "#b45521",
        "count_rescaled": "#777777",
        "matched_panel": "#638030",
    }
    exports = {}

    def save(fig, name):
        for extension in ["pdf", "svg", "png"]:
            path = dest / (name + "." + extension)
            options = {"dpi": 170} if extension == "png" else {}
            if extension == "pdf":
                options["metadata"] = {
                    "CreationDate": None,
                    "ModDate": None,
                    "Creator": "Original study07 figure",
                }
            if extension == "svg":
                options["metadata"] = {"Date": None}
            fig.savefig(path, **options)
            if extension == "svg":
                path.write_bytes(
                    (
                        "\n".join(
                            line.rstrip()
                            for line in path.read_text(encoding="utf-8").splitlines()
                        )
                        + "\n"
                    ).encode()
                )
            exports[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(8.5, 4.8), sharey=True)
    fig.subplots_adjust(left=0.09, right=0.985, bottom=0.32, top=0.8, wspace=0.13)
    fig.suptitle(
        "Synthetic prior-year gaps inflate displayed growth",
        y=0.975,
        fontweight="bold",
        fontsize=14,
    )
    fig.text(
        0.5,
        0.89,
        "About 10% of units masked; 74.1–74.5% of their baseline boardings",
        ha="center",
        fontsize=10,
    )
    for ax, year in zip(axes, [2023, 2024, 2025]):
        rows = sorted(
            [
                r
                for r in points
                if int(r["year"]) == year
                and r["fraction"] == "1/10"
                and r["ranking"] == "baseline_volume_desc"
                and r["masked_side"] == "prior"
                and r["view"] == "zero_fill"
            ],
            key=lambda r: int(r["month"]),
        )
        values["growth"][str(year)] = {}
        for view in ["truth", "zero_fill", "count_rescaled", "matched_panel"]:
            if view == "truth":
                ys = [100 * float(Q(r["truth_growth"])) for r in rows]
            else:
                subset = sorted(
                    [
                        r
                        for r in points
                        if int(r["year"]) == year
                        and r["fraction"] == "1/10"
                        and r["ranking"] == "baseline_volume_desc"
                        and r["masked_side"] == "prior"
                        and r["view"] == view
                    ],
                    key=lambda r: int(r["month"]),
                )
                ys = [100 * float(Q(r["growth"])) for r in subset]
            (line,) = ax.plot(
                range(1, 13),
                ys,
                label=names[view],
                color=colors[view],
                linewidth=2 if view == "truth" else 1.7,
                linestyle="--" if view == "matched_panel" else "-",
                marker="o" if view == "truth" else None,
                markersize=3,
            )
            values["growth"][str(year)][view] = {
                "x": list(map(float, line.get_xdata())),
                "y": list(map(float, line.get_ydata())),
            }
        ax.set_title(str(year), fontweight="bold", loc="left")
        ax.axhline(0, color="#aaaaaa", linewidth=0.7, linestyle=":")
        ax.grid(axis="y", alpha=0.18)
        ax.set_xticks([1, 3, 6, 9, 12])
        ax.set_xlabel("Calendar month")
    axes[0].set_ylabel("Year-over-year published-count growth (%)")
    fig.legend(
        *axes[0].get_legend_handles_labels(),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.06),
        ncol=2,
        frameon=False,
        fontsize=9
    )
    fig.text(
        0.5,
        0.025,
        "Fixed complete-record cohorts; synthetic gaps, not observed reporting behavior or passenger benefit.",
        ha="center",
        fontsize=8,
    )
    save(fig, "primary_growth")
    ranks = ["baseline_volume_desc", "baseline_volume_asc", "identifier"]
    fractions = ["1/20", "1/10", "1/5"]
    views = ["zero_fill", "count_rescaled", "matched_panel"]
    matrices = {
        view: np.array(
            [
                [
                    float(
                        Q(
                            next(
                                r["mae_pp"]
                                for r in settings
                                if r["fraction"] == fraction
                                and r["ranking"] == rank
                                and r["masked_side"] == "prior"
                                and r["view"] == view
                            )
                        )
                    )
                    for fraction in fractions
                ]
                for rank in ranks
            ]
        )
        for view in views
    }
    fig, axes = plt.subplots(1, 3, figsize=(8.5, 4.1), sharey=True)
    fig.subplots_adjust(left=0.22, right=0.85, bottom=0.27, top=0.76, wspace=0.1)
    fig.suptitle(
        "Growth error depends on which service units are missing",
        y=0.97,
        fontweight="bold",
        fontsize=13,
    )
    fig.text(
        0.5,
        0.86,
        "Mean absolute error, percentage points; 36 held months, prior-year-only gaps",
        ha="center",
        fontsize=9,
    )
    maximum = max(float(np.max(matrix)) for matrix in matrices.values())
    for ax, view in zip(axes, views):
        matrix = matrices[view]
        artist = ax.imshow(matrix, vmin=0, vmax=maximum, cmap="viridis", aspect="auto")
        values["errors"][view] = artist.get_array().tolist()
        ax.set_xticks(range(3), ["5%", "10%", "20%"])
        ax.set_title(names[view], fontsize=10, fontweight="bold")
        ax.set_yticks(
            range(3), ["Largest baseline", "Smallest baseline", "Identifier order"]
        )
        for i in range(3):
            for j in range(3):
                background = artist.cmap(artist.norm(matrix[i, j]))[:3]
                fg = (
                    "black"
                    if (luminance(background) + 0.05) / 0.05
                    >= 1.05 / (luminance(background) + 0.05)
                    else "white"
                )
                text = ax.text(
                    j,
                    i,
                    format(matrix[i, j], ".2f"),
                    ha="center",
                    va="center",
                    color=fg,
                    fontsize=9,
                )
                values["annotations"].append(
                    dict(
                        view=view,
                        row=i,
                        column=j,
                        text=text.get_text(),
                        foreground=list(to_rgb(text.get_color())),
                        background=list(background),
                    )
                )
    fig.colorbar(
        artist,
        cax=fig.add_axes([0.88, 0.27, 0.015, 0.49]),
        label="Error (percentage points)",
    )
    fig.text(0.5, 0.13, "Masked share of agency-service units", ha="center")
    fig.text(
        0.5,
        0.035,
        "Linear shared color scale; full 27-gap grid and exact monthly errors remain in results/.",
        ha="center",
        fontsize=8,
    )
    save(fig, "gap_sensitivity")
    fig, axes = plt.subplots(1, 3, figsize=(8.5, 4.1), sharey=True)
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.27, top=0.77, wspace=0.1)
    fig.suptitle(
        "Containing the benchmark does not validate the cap",
        y=0.97,
        fontweight="bold",
        fontsize=13,
    )
    fig.text(
        0.5,
        0.86,
        "Each panel: all 972 held synthetic cases; 324 per masked-year side",
        ha="center",
        fontsize=9,
    )
    for ax, gamma in zip(axes, ["1", "2", "4"]):
        rows = [
            next(
                r for r in intervals if r["gamma"] == gamma and r["masked_side"] == side
            )
            for side in ["prior", "current", "both"]
        ]
        values["bounds"][gamma] = {}
        for key, label, color, offset in [
            ("truth_contained", "Benchmark inside", "#16546c", -0.18),
            ("assumptions_valid", "Every hidden value under cap", "#b45521", 0.18),
        ]:
            heights = [100 * int(r[key]) / int(r["n"]) for r in rows]
            bars = ax.bar(
                np.arange(3) + offset,
                heights,
                width=0.34,
                label=label,
                color=color,
                hatch="//" if key == "assumptions_valid" else None,
            )
            values["bounds"][gamma][key] = [bar.get_height() for bar in bars]
        ax.set_title("Cap = " + gamma + " × 2019 month", fontsize=10, fontweight="bold")
        ax.set_xticks(range(3), ["Prior", "Current", "Both"])
        ax.set_ylim(0, 105)
        ax.grid(axis="y", alpha=0.15)
    axes[0].set_ylabel("Share of finite cases (%)")
    fig.legend(
        *axes[0].get_legend_handles_labels(),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.1),
        ncol=2,
        frameon=False,
        fontsize=9
    )
    fig.text(
        0.5,
        0.035,
        "Illustrative per-unit caps; containment in this synthetic benchmark is not confidence or future coverage.",
        ha="center",
        fontsize=8,
    )
    save(fig, "bound_assumptions")
    (dest / "ARTIST_VALUES.json").write_text(
        json.dumps(values, indent=2) + "\n", encoding="utf-8"
    )
    (dest / "MANIFEST.json").write_text(
        json.dumps(exports, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            dict(
                state="FIGURES_CREATED_PENDING_INDEPENDENT_CHECK", exports=len(exports)
            )
        )
    )


if __name__ == "__main__":
    main()
