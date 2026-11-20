#!/usr/bin/env python3
"""Analyze precursors (D-1..D-N) before low/high Deep Sleep nights."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

METRICS = [
    "Active Calories",
    "Total Steps",
    "Distance",
    "Resting Heart Rate",
    "Average Stress Level",
    "REM Sleep",
    "Measurable Asleep Duration",
]

METRIC_LABELS = {
    "Active Calories": "Active Calories",
    "Total Steps": "Total Steps",
    "Distance": "Distance (m)",
    "Resting Heart Rate": "Resting HR",
    "Average Stress Level": "Avg Stress",
    "REM Sleep": "REM Sleep (min)",
    "Measurable Asleep Duration": "Total Sleep (min)",
}


@dataclass
class Thresholds:
    percentile: float
    p_low: float
    p_high: float
    low_seconds: float | None = None
    high_seconds: float | None = None

    @property
    def low_minutes(self) -> float:
        return self.effective_low / 60

    @property
    def high_minutes(self) -> float:
        return self.effective_high / 60

    @property
    def effective_low(self) -> float:
        return self.low_seconds if self.low_seconds is not None else self.p_low

    @property
    def effective_high(self) -> float:
        return self.high_seconds if self.high_seconds is not None else self.p_high


@dataclass
class ComparisonRow:
    extreme: str
    metric: str
    lag: int
    pre_mean: float
    baseline_mean: float
    diff_pct: float
    p_value: float
    z_score: float
    significant: bool


@dataclass
class AnalysisResult:
    df: pd.DataFrame
    thresholds: Thresholds
    median_deep: float
    low_nights: pd.DataFrame
    high_nights: pd.DataFrame
    baseline: pd.DataFrame
    pre_low: pd.DataFrame
    pre_high: pd.DataFrame
    comparisons: list[ComparisonRow] = field(default_factory=list)
    mirror_rows: list[dict] = field(default_factory=list)
    top_low: list[dict] = field(default_factory=list)
    top_high: list[dict] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Analyze precursors before low/high Deep Sleep nights."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=script_dir / "garmin_data_extended.csv",
        help="Path to Garmin CSV export",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=script_dir / "output",
        help="Directory for generated charts",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of days to analyze from the latest date in CSV",
    )
    parser.add_argument(
        "--percentile",
        type=float,
        default=10.0,
        help="Symmetric percentile for low/high thresholds (default: P10/P90)",
    )
    parser.add_argument(
        "--threshold-minutes-low",
        type=float,
        default=None,
        help="Fixed low threshold in minutes (overrides percentile for low)",
    )
    parser.add_argument(
        "--threshold-minutes-high",
        type=float,
        default=None,
        help="Fixed high threshold in minutes (overrides percentile for high)",
    )
    parser.add_argument(
        "--lag-days",
        type=int,
        default=3,
        help="How many days before extreme night to include (D-1..D-N)",
    )
    return parser.parse_args()


def load_data(csv_path: Path, days: int) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["Date"] = pd.to_datetime(df["Date"])
    for col in METRICS + ["Deep Sleep"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("Date").reset_index(drop=True)
    end_date = df["Date"].max()
    start_date = end_date - pd.Timedelta(days=days - 1)
    return df[df["Date"] >= start_date].copy()


def compute_thresholds(
    df: pd.DataFrame,
    percentile: float,
    low_minutes: float | None,
    high_minutes: float | None,
) -> Thresholds:
    deep = df["Deep Sleep"].dropna()
    low_pct = percentile
    high_pct = 100 - percentile
    p_low = float(np.percentile(deep, low_pct))
    p_high = float(np.percentile(deep, high_pct))
    return Thresholds(
        percentile=percentile,
        p_low=p_low,
        p_high=p_high,
        low_seconds=low_minutes * 60 if low_minutes is not None else None,
        high_seconds=high_minutes * 60 if high_minutes is not None else None,
    )


def classify_nights(df: pd.DataFrame, thresholds: Thresholds) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    low_mask = df["Deep Sleep"] <= thresholds.effective_low
    high_mask = df["Deep Sleep"] >= thresholds.effective_high
    normal_mask = ~low_mask & ~high_mask & df["Deep Sleep"].notna()

    return (
        df[low_mask].copy(),
        df[high_mask].copy(),
        df[normal_mask].copy(),
    )


def build_pre_window(
    df: pd.DataFrame,
    extreme_dates: pd.Series,
    lag_days: int,
    extreme_label: str,
) -> pd.DataFrame:
    by_date = df.set_index("Date")
    records: list[dict] = []

    for extreme_date in extreme_dates:
        for lag in range(1, lag_days + 1):
            pre_date = extreme_date - pd.Timedelta(days=lag)
            if pre_date not in by_date.index:
                continue
            row = by_date.loc[pre_date].to_dict()
            records.append(
                {
                    "extreme_date": extreme_date,
                    "pre_date": pre_date,
                    "lag": lag,
                    "extreme": extreme_label,
                    **{m: row.get(m) for m in METRICS},
                }
            )

    return pd.DataFrame(records)


def exclude_pre_window_dates(baseline: pd.DataFrame, pre_df: pd.DataFrame) -> pd.DataFrame:
    if pre_df.empty:
        return baseline
    exclude = set(pre_df["pre_date"])
    return baseline[~baseline["Date"].isin(exclude)].copy()


def compare_group(
    pre_df: pd.DataFrame,
    baseline: pd.DataFrame,
    extreme_label: str,
    lag_days: int,
) -> list[ComparisonRow]:
    rows: list[ComparisonRow] = []

    for metric in METRICS:
        base_vals = baseline[metric].dropna()
        if base_vals.empty:
            continue
        base_mean = float(base_vals.mean())
        base_std = float(base_vals.std(ddof=0))
        if base_std == 0:
            base_std = 1e-9

        for lag in range(1, lag_days + 1):
            pre_vals = pre_df.loc[pre_df["lag"] == lag, metric].dropna()
            if pre_vals.empty:
                continue

            pre_mean = float(pre_vals.mean())
            diff_pct = 100 * (pre_mean - base_mean) / base_mean if base_mean else 0.0
            z_score = (pre_mean - base_mean) / base_std

            if len(pre_vals) >= 3 and len(base_vals) >= 3:
                _, p_value = stats.mannwhitneyu(pre_vals, base_vals, alternative="two-sided")
            else:
                p_value = 1.0

            rows.append(
                ComparisonRow(
                    extreme=extreme_label,
                    metric=metric,
                    lag=lag,
                    pre_mean=pre_mean,
                    baseline_mean=base_mean,
                    diff_pct=diff_pct,
                    p_value=float(p_value),
                    z_score=z_score,
                    significant=p_value < 0.05,
                )
            )

    return rows


def build_mirror_rows(comparisons: list[ComparisonRow]) -> list[dict]:
    low_by_key = {(r.metric, r.lag): r for r in comparisons if r.extreme == "low"}
    high_by_key = {(r.metric, r.lag): r for r in comparisons if r.extreme == "high"}
    mirror: list[dict] = []

    for key in sorted(set(low_by_key) & set(high_by_key)):
        low_r = low_by_key[key]
        high_r = high_by_key[key]
        opposite = (low_r.diff_pct > 0 and high_r.diff_pct < 0) or (
            low_r.diff_pct < 0 and high_r.diff_pct > 0
        )
        mirror.append(
            {
                "metric": low_r.metric,
                "lag": low_r.lag,
                "low_diff_pct": low_r.diff_pct,
                "high_diff_pct": high_r.diff_pct,
                "low_p": low_r.p_value,
                "high_p": high_r.p_value,
                "opposite": opposite,
            }
        )

    mirror.sort(key=lambda r: (not r["opposite"], abs(r["low_diff_pct"]) + abs(r["high_diff_pct"])), reverse=True)
    return mirror


def top_extreme_nights(
    extreme_df: pd.DataFrame,
    pre_df: pd.DataFrame,
    baseline: pd.DataFrame,
    comparisons: list[ComparisonRow],
    extreme_label: str,
    n: int = 10,
) -> list[dict]:
    scored = []
    for _, row in extreme_df.iterrows():
        extreme_date = row["Date"]
        night_pre = pre_df[pre_df["extreme_date"] == extreme_date]
        score = 0.0
        for _, pre_row in night_pre.iterrows():
            lag = int(pre_row["lag"])
            for metric in METRICS:
                val = pre_row.get(metric)
                if pd.isna(val):
                    continue
                comp = next(
                    (
                        c
                        for c in comparisons
                        if c.extreme == extreme_label and c.metric == metric and c.lag == lag
                    ),
                    None,
                )
                if comp is None or comp.baseline_mean == 0:
                    continue
                score += abs((val - comp.baseline_mean) / comp.baseline_mean)

        scored.append(
            {
                "date": extreme_date.strftime("%Y-%m-%d"),
                "deep_sleep_min": row["Deep Sleep"] / 60,
                "score": score,
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:n]


def run_analysis(args: argparse.Namespace) -> AnalysisResult:
    df = load_data(args.csv, args.days)
    thresholds = compute_thresholds(
        df,
        args.percentile,
        args.threshold_minutes_low,
        args.threshold_minutes_high,
    )
    low_nights, high_nights, baseline = classify_nights(df, thresholds)

    pre_low = build_pre_window(df, low_nights["Date"], args.lag_days, "low")
    pre_high = build_pre_window(df, high_nights["Date"], args.lag_days, "high")

    baseline_low = exclude_pre_window_dates(baseline, pre_low)
    baseline_high = exclude_pre_window_dates(baseline, pre_high)

    comparisons = compare_group(pre_low, baseline_low, "low", args.lag_days)
    comparisons.extend(compare_group(pre_high, baseline_high, "high", args.lag_days))

    mirror_rows = build_mirror_rows(comparisons)
    top_low = top_extreme_nights(low_nights, pre_low, baseline_low, comparisons, "low")
    top_high = top_extreme_nights(high_nights, pre_high, baseline_high, comparisons, "high")

    median_deep = float(df["Deep Sleep"].median())

    return AnalysisResult(
        df=df,
        thresholds=thresholds,
        median_deep=median_deep,
        low_nights=low_nights,
        high_nights=high_nights,
        baseline=baseline,
        pre_low=pre_low,
        pre_high=pre_high,
        comparisons=comparisons,
        mirror_rows=mirror_rows,
        top_low=top_low,
        top_high=top_high,
    )


def format_minutes(seconds: float) -> str:
    return f"{seconds / 60:.0f} min ({seconds:.0f} s)"


def print_report(result: AnalysisResult, args: argparse.Namespace) -> None:
    th = result.thresholds
    df = result.df

    print("=" * 72)
    print("DEEP SLEEP PRECURSOR ANALYSIS")
    print("=" * 72)
    print(f"CSV: {args.csv}")
    print(f"Date range: {df['Date'].min().date()} .. {df['Date'].max().date()} ({len(df)} days)")
    print(f"WARNING: Latest data ends on {df['Date'].max().date()} — refresh CSV for recent nights.")
    print()
    print("Thresholds:")
    print(f"  Percentile setting: P{th.percentile:.0f} / P{100 - th.percentile:.0f}")
    print(f"  Low  (<=): {format_minutes(th.effective_low)}")
    print(f"  High (>=): {format_minutes(th.effective_high)}")
    print(f"  Median Deep Sleep: {format_minutes(result.median_deep)}")
    print()
    print(f"Low nights:  {len(result.low_nights)}")
    print(f"High nights: {len(result.high_nights)}")
    print(f"Normal nights (baseline): {len(result.baseline)}")
    print(f"Pre-window lag days: D-1 .. D-{args.lag_days}")
    print()

    for extreme in ("low", "high"):
        label = extreme.upper()
        print("-" * 72)
        print(f"{label} EXTREME — pre-window vs baseline")
        print("-" * 72)
        print(f"{'Metric':<28} {'Lag':>4} {'Pre':>10} {'Base':>10} {'Diff%':>8} {'p':>8} {'Sig':>5}")
        for row in sorted(
            [r for r in result.comparisons if r.extreme == extreme],
            key=lambda r: (r.metric, r.lag),
        ):
            sig = "yes" if row.significant else "no"
            print(
                f"{METRIC_LABELS.get(row.metric, row.metric):<28} "
                f"D-{row.lag:>2} {row.pre_mean:10.1f} {row.baseline_mean:10.1f} "
                f"{row.diff_pct:+8.1f} {row.p_value:8.4f} {sig:>5}"
            )
        print()

    print("-" * 72)
    print("MIRROR COMPARISON — opposite patterns (low vs high precursors)")
    print("-" * 72)
    opposite = [r for r in result.mirror_rows if r["opposite"]]
    if not opposite:
        print("No clearly opposite patterns found.")
    else:
        print(f"{'Metric':<28} {'Lag':>4} {'Low%':>8} {'High%':>8} {'Low p':>8} {'High p':>8}")
        for row in opposite[:15]:
            print(
                f"{METRIC_LABELS.get(row['metric'], row['metric']):<28} "
                f"D-{row['lag']:>2} {row['low_diff_pct']:+8.1f} {row['high_diff_pct']:+8.1f} "
                f"{row['low_p']:8.4f} {row['high_p']:8.4f}"
            )
    print()

    for label, items in (("LOW", result.top_low), ("HIGH", result.top_high)):
        print("-" * 72)
        print(f"TOP {label} NIGHTS — strongest precursor deviations")
        print("-" * 72)
        for item in items:
            print(f"  {item['date']}  deep={item['deep_sleep_min']:.0f} min  score={item['score']:.2f}")
        print()


def display_value(metric: str, value: float) -> float:
    if metric in ("REM Sleep", "Measurable Asleep Duration"):
        return value / 60
    return value


def plot_timeline(result: AnalysisResult, output_dir: Path) -> None:
    df = result.df.sort_values("Date")
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(df["Date"], df["Deep Sleep"] / 60, color="#888888", linewidth=1, label="Deep Sleep")

    low_dates = set(result.low_nights["Date"])
    high_dates = set(result.high_nights["Date"])
    low_pts = df[df["Date"].isin(low_dates)]
    high_pts = df[df["Date"].isin(high_dates)]

    ax.scatter(low_pts["Date"], low_pts["Deep Sleep"] / 60, color="#d62728", s=40, zorder=3, label="Low (P10)")
    ax.scatter(high_pts["Date"], high_pts["Deep Sleep"] / 60, color="#2ca02c", s=40, zorder=3, label="High (P90)")

    th = result.thresholds
    ax.axhline(th.effective_low / 60, color="#d62728", linestyle="--", alpha=0.5, linewidth=1)
    ax.axhline(th.effective_high / 60, color="#2ca02c", linestyle="--", alpha=0.5, linewidth=1)
    ax.axhline(result.median_deep / 60, color="#1f77b4", linestyle=":", alpha=0.7, linewidth=1, label="Median")

    ax.set_xlabel("Date")
    ax.set_ylabel("Deep Sleep (minutes)")
    ax.set_title("Deep Sleep Timeline — Low and High Extremes")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "timeline_extremes.png", dpi=150)
    plt.close(fig)


def plot_heatmap(result: AnalysisResult, extreme: str, output_dir: Path) -> None:
    rows = [r for r in result.comparisons if r.extreme == extreme]
    if not rows:
        return

    lags = sorted({r.lag for r in rows})
    metrics = METRICS
    matrix = np.full((len(metrics), len(lags)), np.nan)

    for r in rows:
        i = metrics.index(r.metric)
        j = lags.index(r.lag)
        matrix[i, j] = r.diff_pct

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(matrix, aspect="auto", cmap="RdBu_r", vmin=-30, vmax=30)
    ax.set_xticks(range(len(lags)))
    ax.set_xticklabels([f"D-{lag}" for lag in lags])
    ax.set_yticks(range(len(metrics)))
    ax.set_yticklabels([METRIC_LABELS.get(m, m) for m in metrics])
    ax.set_title(f"Precursor diff vs baseline (%) — {extreme.upper()} extreme")

    for i in range(len(metrics)):
        for j in range(len(lags)):
            val = matrix[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:+.0f}", ha="center", va="center", fontsize=8)

    fig.colorbar(im, ax=ax, label="Diff %")
    fig.tight_layout()
    fig.savefig(output_dir / f"heatmap_{extreme}.png", dpi=150)
    plt.close(fig)


def plot_heatmap_mirror(result: AnalysisResult, output_dir: Path) -> None:
    lags = sorted({r.lag for r in result.comparisons})
    metrics = METRICS
    low_matrix = np.full((len(metrics), len(lags)), np.nan)
    high_matrix = np.full((len(metrics), len(lags)), np.nan)

    for r in result.comparisons:
        i = metrics.index(r.metric)
        j = lags.index(r.lag)
        if r.extreme == "low":
            low_matrix[i, j] = r.diff_pct
        else:
            high_matrix[i, j] = r.diff_pct

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    for ax, matrix, title in zip(
        axes,
        [low_matrix, high_matrix],
        ["LOW extreme precursors", "HIGH extreme precursors"],
    ):
        im = ax.imshow(matrix, aspect="auto", cmap="RdBu_r", vmin=-30, vmax=30)
        ax.set_xticks(range(len(lags)))
        ax.set_xticklabels([f"D-{lag}" for lag in lags])
        ax.set_yticks(range(len(metrics)))
        ax.set_yticklabels([METRIC_LABELS.get(m, m) for m in metrics])
        ax.set_title(title)
        for i in range(len(metrics)):
            for j in range(len(lags)):
                val = matrix[i, j]
                if not np.isnan(val):
                    ax.text(j, i, f"{val:+.0f}", ha="center", va="center", fontsize=8)

    fig.colorbar(im, ax=axes.ravel().tolist(), label="Diff %")
    fig.suptitle("Mirror comparison — low vs high precursors")
    fig.subplots_adjust(top=0.92, wspace=0.25)
    fig.savefig(output_dir / "heatmap_mirror.png", dpi=150)
    plt.close(fig)


def plot_boxplots(
    result: AnalysisResult,
    extreme: str,
    baseline: pd.DataFrame,
    pre_df: pd.DataFrame,
    output_dir: Path,
    lag_days: int,
) -> None:
    key_metrics = ["Active Calories", "Total Steps", "Average Stress Level", "Measurable Asleep Duration"]
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    for ax, metric in zip(axes, key_metrics):
        baseline_vals = [display_value(metric, v) for v in baseline[metric].dropna()]
        groups = [baseline_vals]
        labels = ["Baseline"]
        for lag in range(1, lag_days + 1):
            pre_vals = pre_df.loc[pre_df["lag"] == lag, metric].dropna()
            groups.append([display_value(metric, v) for v in pre_vals])
            labels.append(f"D-{lag}")

        ax.boxplot(groups, tick_labels=labels)
        ax.set_title(METRIC_LABELS.get(metric, metric))
        ax.grid(True, alpha=0.3)

    fig.suptitle(f"Precursor distributions — {extreme.upper()} extreme nights")
    fig.tight_layout()
    fig.savefig(output_dir / f"boxplot_{extreme}.png", dpi=150)
    plt.close(fig)


def generate_plots(result: AnalysisResult, args: argparse.Namespace) -> None:
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_low = exclude_pre_window_dates(result.baseline, result.pre_low)
    baseline_high = exclude_pre_window_dates(result.baseline, result.pre_high)

    plot_timeline(result, output_dir)
    plot_heatmap(result, "low", output_dir)
    plot_heatmap(result, "high", output_dir)
    plot_heatmap_mirror(result, output_dir)
    plot_boxplots(result, "low", baseline_low, result.pre_low, output_dir, args.lag_days)
    plot_boxplots(result, "high", baseline_high, result.pre_high, output_dir, args.lag_days)


def main() -> None:
    args = parse_args()
    if not args.csv.exists():
        raise SystemExit(f"CSV not found: {args.csv}")

    result = run_analysis(args)
    print_report(result, args)
    generate_plots(result, args)
    print(f"Charts saved to: {args.output.resolve()}")


if __name__ == "__main__":
    main()
