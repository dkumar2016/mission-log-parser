"""Mission log parser: reads a spacecraft operations log, skips malformed lines
with a reason, counts events by level and subsystem, and writes reports."""

from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

VALID_LEVELS = {"INFO", "WARN", "ERROR"}
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
INPUT_PATH = Path(__file__).resolve().parent / "data" / "ops_log.txt"


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



if __name__ == "__main__":
    good, bad = read_log(INPUT_PATH)
    counts = count_events(good)
    first, last = time_span(good)

    print(f"Read {len(good)} valid and {len(bad)} malformed lines")
    for entry in bad:
        print(
            f"Line {entry['line_number']}: {entry['reason']} "
            f"({entry['line']!r})"
        )
    print(f"Time span: {first} to {last}\n")
    print("By level:     ", dict(counts["by_level"]))
    print("By subsystem: ", counts["by_subsystem"].most_common())
    print("EPS errors:   ", counts["by_subsystem_level"][("EPS", "ERROR")])