"""Mission log parser: reads a spacecraft operations log, skips malformed lines
with a reason, counts events by level and subsystem, and writes reports."""

from datetime import datetime, timezone
from collections import Counter
from pathlib import Path
import json
import os


VALID_LEVELS = {"INFO", "WARN", "ERROR"}          # used by parse_log_line
LEVELS = ("INFO", "WARN", "ERROR")                # fixed output order
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "data" / "ops_log.txt"
OUTPUT_DIR = BASE_DIR / "output"

def parse_log_line(line):
    """Parse 'TIMESTAMP [SUBSYSTEM] LEVEL message' into a dict.

    Raise ValueError with a reason if the line is malformed.
    """
    parts = line.strip().split(maxsplit=3)

    if len(parts) < 4:
        raise ValueError(f"too few fields: expected 4, got {len(parts)}")

    ts_text, sub_text, level, message = parts

    try:
        timestamp = datetime.strptime(ts_text, TIMESTAMP_FORMAT).replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise ValueError(f"invalid timestamp (expected YYYY-MM-DDTHH:MM:SSZ): {ts_text!r}") from None

    if not sub_text.startswith("[") or not sub_text.endswith("]"):
        raise ValueError(f"invalid subsystem format: {sub_text!r}")

    subsystem = sub_text[1:-1]
    if not subsystem:
        raise ValueError("subsystem must not be empty")

    if level not in VALID_LEVELS:
        raise ValueError(f"invalid level (expected INFO, WARN or ERROR): {level!r}")

    return {
        "timestamp": timestamp,
        "subsystem": subsystem,
        "level": level,
        "message": message,
    }


def read_log(path):
    """Read a log file, returning valid records and malformed-line details.

    Malformed entries are dictionaries containing the 1-based line number,
    original line text, and the parse failure reason.
    """
    records = []
    malformed = []

    with open(path, encoding="utf-8") as log_file:
        for line_number, line in enumerate(log_file, start=1):
            try:
                records.append(parse_log_line(line))
            except ValueError as error:
                malformed.append({
                    "line_number": line_number,
                    "line": line.rstrip("\r\n"),
                    "reason": str(error),
                })

    return records, malformed


def count_events(records):
    """Count records by level, subsystem, and subsystem/level pair."""
    return {
        "by_level": Counter(r["level"] for r in records),
        "by_subsystem": Counter(r["subsystem"] for r in records),
        "by_subsystem_level": Counter(
            (r["subsystem"], r["level"]) for r in records
        ),
    }


def time_span(records):
    """Return the earliest and latest timestamps in the records."""
    timestamps = (r["timestamp"] for r in records)
    first = min(timestamps)
    last = max(r["timestamp"] for r in records)
    return first, last

## Errors

def format_record(r):
    """Rebuild the original log line from a parsed record."""
    return f"{r['timestamp']:%Y-%m-%dT%H:%M:%SZ} [{r['subsystem']}] {r['level']} {r['message']}"


def write_errors(records, path):
    """Write every ERROR record to path, one per line, in time order."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    errors = [r for r in records if r["level"] == "ERROR"]
    errors.sort(key=lambda r: r["timestamp"])
    with open(path, "w", encoding="utf-8") as f:
        for r in errors:
            f.write(format_record(r) + "\n")
    return len(errors)



#Summary.json

def subsystem_level_table(counts):
    """Turn the (subsystem, level) Counter into {subsystem: {level: count}}."""
    table = {}
    for sub in sorted(counts["by_subsystem"]):
        table[sub] = {level: counts["by_subsystem_level"][(sub, level)] for level in LEVELS}
    return table


def write_summary(counts, first, last, n_valid, n_malformed, path):
    """Write counts and time span as JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    summary = {
        "total_lines": n_valid + n_malformed,
        "valid": n_valid,
        "malformed": n_malformed,
        "first_timestamp": first.isoformat(),
        "last_timestamp": last.isoformat(),
        "by_level": {level: counts["by_level"][level] for level in LEVELS},
        "by_subsystem": dict(counts["by_subsystem"].most_common()),
        "by_subsystem_level": subsystem_level_table(counts),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary



#Report

def build_report(counts, first, last, n_valid, bad, source="data/ops_log.txt"):
    """Return the daily report as a list of text lines."""
    lines = [
        "MISSION LOG DAILY REPORT",
        "========================",
        f"Source:     {source}",
        f"Time span:  {first:%Y-%m-%d %H:%M:%S} UTC to {last:%Y-%m-%d %H:%M:%S} UTC",
        f"Lines:      {n_valid + len(bad)} total, {n_valid} valid, {len(bad)} malformed",
        "",
        "EVENTS BY LEVEL",
    ]
    for level in LEVELS:
        lines.append(f"  {level:<8}{counts['by_level'][level]:>5}")

    lines += ["", "EVENTS BY SUBSYSTEM",
              f"  {'Subsystem':<10}{'INFO':>6}{'WARN':>6}{'ERROR':>7}{'Total':>7}"]
    table = subsystem_level_table(counts)
    for sub, row in table.items():
        lines.append(f"  {sub:<10}{row['INFO']:>6}{row['WARN']:>6}{row['ERROR']:>7}{sum(row.values()):>7}")
    col = {level: sum(row[level] for row in table.values()) for level in LEVELS}
    lines.append(f"  {'Total':<10}{col['INFO']:>6}{col['WARN']:>6}{col['ERROR']:>7}{sum(col.values()):>7}")

    lines += ["", f"MALFORMED LINES ({len(bad)})"]
    for b in bad:
        lines.append(f"  line {b['line_number']:>3}: {b['reason']}")
    return lines


def write_report(counts, first, last, n_valid, bad, path):
    """Write the daily report to path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = build_report(counts, first, last, n_valid, bad)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return lines



if __name__ == "__main__":
    good, bad = read_log(INPUT_PATH)
    counts = count_events(good)
    first, last = time_span(good)

    n_errors = write_errors(good, os.path.join(OUTPUT_DIR, "errors.txt"))
    write_summary(counts, first, last, len(good), len(bad), os.path.join(OUTPUT_DIR, "summary.json"))
    write_report(counts, first, last, len(good), bad, os.path.join(OUTPUT_DIR, "report.txt"))

    print(f"Read {len(good)} valid and {len(bad)} malformed lines")
    print(f"Wrote {n_errors} errors, summary.json and report.txt to {OUTPUT_DIR}")