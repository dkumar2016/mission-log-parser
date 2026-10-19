"""Tests for log_parser.py: parsing, reading, counting and the three output files."""


import json
from datetime import datetime, timezone
import pytest

from log_parser import (
    INPUT_PATH,
    parse_log_line,
    read_log,
    count_events,
    time_span,
    format_record,
    write_errors,
    write_summary,
    build_report,
    write_report,
)

VALID_LINE = "2026-03-01T04:12:09Z [ADCS] WARN reaction wheel 2 speed high"


# ---------- parse_log_line: valid lines ----------

def test_parse_valid_line_fields():
    record = parse_log_line(VALID_LINE)
    assert record["subsystem"] == "ADCS"
    assert record["level"] == "WARN"
    assert record["message"] == "reaction wheel 2 speed high"   # spaces kept


def test_parse_timestamp_is_utc_datetime():
    record = parse_log_line(VALID_LINE)
    assert record["timestamp"] == datetime(2026, 3, 1, 4, 12, 9, tzinfo=timezone.utc)


def test_parse_ignores_trailing_newline():
    assert parse_log_line(VALID_LINE + "\n") == parse_log_line(VALID_LINE)


# ---------- parse_log_line: the 10 malformed lines ----------

@pytest.mark.parametrize("line, reason", [
    ("", "too few fields"),
    ("2026-03-01T05:00:00Z [EPS] battery nominal", "invalid level"),
    ("2026-13-45T25:00:00Z [OBC] INFO reboot complete", "invalid timestamp"),
    ("2026-03-01T06:00:00Z ADCS INFO mode change", "invalid subsystem format"),
    ("2026-03-01T07:00:00Z [COMMS] DEBUGX signal check", "invalid level"),
    ("2026-03-01T08:00:00Z [PRO", "too few fields"),
    ("03/01/2026 09:00 [THERMAL] INFO heater 1 on", "invalid timestamp"),
    ("2026-03-01T10:00:00Z [] INFO empty subsystem", "subsystem must not be empty"),
    ("2026-03-01T11:00:00Z [EPS] WARN", "too few fields"),
    ("garbage line with no structure", "invalid timestamp"),
])
def test_parse_malformed_lines(line, reason):
    with pytest.raises(ValueError, match=reason):
        parse_log_line(line)


# ---------- read_log on the real data file ----------

def test_read_log_counts():
    good, bad = read_log(INPUT_PATH)
    assert len(good) == 490
    assert len(bad) == 10


def test_read_log_malformed_line_numbers():
    _, bad = read_log(INPUT_PATH)
    assert [b["line_number"] for b in bad] == [68, 163, 166, 179, 207, 373, 380, 391, 446, 451]


# ---------- counts and time span (answer key from the generated log) ----------

@pytest.fixture
def records():
    good, _ = read_log(INPUT_PATH)
    return good


def test_counts_by_level(records):
    counts = count_events(records)
    assert dict(counts["by_level"]) == {"INFO": 388, "WARN": 76, "ERROR": 26}


def test_counts_by_subsystem(records):
    counts = count_events(records)
    assert counts["by_subsystem"].most_common(1) == [("OBC", 98)]
    assert sum(counts["by_subsystem"].values()) == 490


def test_cross_count_consistent_with_single_counts(records):
    counts = count_events(records)
    for level, n in counts["by_level"].items():
        assert sum(v for (sub, lvl), v in counts["by_subsystem_level"].items() if lvl == level) == n
    for sub, n in counts["by_subsystem"].items():
        assert sum(v for (s, lvl), v in counts["by_subsystem_level"].items() if s == sub) == n


def test_eps_errors(records):
    assert count_events(records)["by_subsystem_level"][("EPS", "ERROR")] == 7


def test_time_span(records):
    first, last = time_span(records)
    assert first == datetime(2026, 3, 1, 0, 1, 27, tzinfo=timezone.utc)
    assert last == datetime(2026, 3, 1, 21, 44, 31, tzinfo=timezone.utc)


# ---------- output files (tmp_path = temporary folder from pytest) ----------

def test_format_record_round_trip():
    assert format_record(parse_log_line(VALID_LINE)) == VALID_LINE


def test_errors_file_matches_original_error_lines(records, tmp_path):
    path = tmp_path / "out" / "errors.txt"
    n = write_errors(records, path)
    written = path.read_text(encoding="utf-8").splitlines()
    with open(INPUT_PATH, encoding="utf-8") as f:
        originals = [line.rstrip("\n") for line in f if "] ERROR " in line]
    assert n == 26
    assert written == originals


def test_summary_json(records, tmp_path):
    counts = count_events(records)
    first, last = time_span(records)
    path = tmp_path / "out" / "summary.json"
    write_summary(counts, first, last, len(records), 10, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["total_lines"] == 500
    assert data["by_level"] == {"INFO": 388, "WARN": 76, "ERROR": 26}
    assert data["by_subsystem_level"]["EPS"]["ERROR"] == 7
    assert data["first_timestamp"] == "2026-03-01T00:01:27+00:00"


def test_report_total_row(records):
    _, bad = read_log(INPUT_PATH)
    counts = count_events(records)
    first, last = time_span(records)
    lines = build_report(counts, first, last, len(records), bad)
    total_row = next(line for line in lines if line.strip().startswith("Total"))
    assert total_row.split()[1:] == ["388", "76", "26", "490"]


def test_report_file_matches_built_report(records, tmp_path):
    _, bad = read_log(INPUT_PATH)
    counts = count_events(records)
    first, last = time_span(records)
    path = tmp_path / "out" / "report.txt"
    lines = write_report(counts, first, last, len(records), bad, path)
    assert path.read_text(encoding="utf-8").splitlines() == lines