#!/usr/bin/env python3
"""Fetch Garmin Connect daily stats and merge into garmin_data_extended.csv."""

from __future__ import annotations

import argparse
import csv
import os
import time
from datetime import date, timedelta
from pathlib import Path

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

FIELDNAMES = [
    "Date",
    "Active Calories",
    "Total Steps",
    "Distance",
    "Min Heart Rate",
    "Max Heart Rate",
    "Resting Heart Rate",
    "Average Stress Level",
    "Deep Sleep",
    "REM Sleep",
    "Measurable Asleep Duration",
]


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Update Garmin CSV export.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=script_dir / "garmin_data_extended.csv",
        help="CSV file to update",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Fetch last N days (full refresh window). Default: only missing dates.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="Delay between API calls in seconds",
    )
    return parser.parse_args()


def load_existing(csv_path: Path) -> dict[str, dict]:
    if not csv_path.exists():
        return {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        return {row["Date"]: row for row in csv.DictReader(f)}


def load_config(path: Path = Path(__file__).with_name("config.env")) -> dict:
    """Read KEY=VALUE pairs from the local, git-ignored config file."""
    if not path.exists():
        return {}
    pairs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            pairs[key.strip()] = value.strip()
    return pairs


def login() -> Garmin:
    config = load_config()
    email = os.environ.get("GARMIN_EMAIL") or config.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD") or config.get("GARMIN_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing Garmin login: copy config.env.example to config.env and fill it in, "
                         "or set GARMIN_EMAIL and GARMIN_PASSWORD.")
    client = Garmin(email, password)
    client.login()
    return client


def fetch_day(client: Garmin, day: date) -> dict:
    summary = client.get_user_summary(day.isoformat())
    sleep = client.get_sleep_data(day.isoformat())
    dto = sleep.get("dailySleepDTO") or {}
    return {
        "Date": day.isoformat(),
        "Active Calories": summary.get("activeKilocalories", ""),
        "Total Steps": summary.get("totalSteps", ""),
        "Distance": summary.get("totalDistanceMeters", ""),
        "Min Heart Rate": summary.get("minHeartRate", ""),
        "Max Heart Rate": summary.get("maxHeartRate", ""),
        "Resting Heart Rate": summary.get("restingHeartRate", ""),
        "Average Stress Level": summary.get("averageStressLevel", ""),
        "Deep Sleep": dto.get("deepSleepSeconds", ""),
        "REM Sleep": dto.get("remSleepSeconds", ""),
        "Measurable Asleep Duration": dto.get("sleepTimeSeconds", ""),
    }


def write_csv(csv_path: Path, rows: dict[str, dict]) -> None:
    ordered = [rows[k] for k in sorted(rows)]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(ordered)


def main() -> None:
    args = parse_args()
    existing = load_existing(args.csv)

    if args.days is not None:
        start = date.today() - timedelta(days=args.days - 1)
    elif existing:
        last = max(date.fromisoformat(d) for d in existing)
        start = last + timedelta(days=1)
    else:
        start = date.today() - timedelta(days=1365)

    end = date.today() - timedelta(days=1)

    if start > end:
        print(f"CSV already up to date (last: {max(existing) if existing else 'n/a'}).")
        return

    total = (end - start).days + 1
    print(f"Fetching {total} days: {start} .. {end}")

    try:
        client = login()
    except (GarminConnectConnectionError, GarminConnectAuthenticationError, GarminConnectTooManyRequestsError) as e:
        raise SystemExit(f"Garmin login failed: {e}") from e

    current = start
    fetched = 0
    while current <= end:
        key = current.isoformat()
        try:
            existing[key] = fetch_day(client, current)
            fetched += 1
            if fetched % 25 == 0 or current == end:
                print(f"  {current} ({fetched}/{total})")
        except Exception as e:
            print(f"  {current} ERROR: {e}")
        current += timedelta(days=1)
        time.sleep(args.delay)

    write_csv(args.csv, existing)
    print(f"Saved {len(existing)} rows to {args.csv}")
    print(f"Date range: {min(existing)} .. {max(existing)}")


if __name__ == "__main__":
    main()
