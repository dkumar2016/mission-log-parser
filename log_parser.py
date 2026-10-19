"""Mission log parser: reads a spacecraft operations log, skips malformed lines
with a reason, counts events by level and subsystem, and writes reports."""

from datetime import datetime, timezone

VALID_LEVELS = {"INFO", "WARN", "ERROR"}
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


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

