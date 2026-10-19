# mission-log-parser

A Python tool that reads a spacecraft operations log, rejects malformed lines with a clear reason, counts events by severity and subsystem, and writes three outputs: an errors file for triage, a JSON summary for other programs, and a readable daily report.

Standard library only. No external packages.

## What it does

1. Reads a log where each line has the form `TIMESTAMP [SUBSYSTEM] LEVEL message`.
2. Validates every line. A malformed line is skipped and recorded with its line number and the reason; it never stops the program.
3. Counts valid events by level (INFO, WARN, ERROR), by subsystem, and by subsystem × level.
4. Writes:
   - `output/errors.txt`: every ERROR line, in time order
   - `output/summary.json`: all counts and the time span, machine-readable
   - `output/report.txt`: a daily report a person can read at the start of a shift

## Repository structure

```
mission-log-parser/
├── make_log.py          generates the sample log (fixed random seed)
├── log_parser.py        the parser, counts and output writers
├── pytest.ini           pytest configuration
├── data/
│   └── ops_log.txt      generated input: 490 valid + 10 malformed lines
├── output/
│   ├── errors.txt
│   ├── summary.json
│   └── report.txt
├── tests/
│   └── test_log_parser.py
└── README.md
```

## Setup and run

Requires Python 3. The parser uses only the standard library; the tests need pytest (included with Anaconda, otherwise `pip install pytest`).

```
git clone git@github.com:dkumar2016/mission-log-parser.git
cd mission-log-parser

py make_log.py       # (re)generate data/ops_log.txt - optional, the file is committed
py log_parser.py     # parse the log, write the three outputs, print the report
pytest -v            # run the 25 tests
```

Running `py log_parser.py` prints the full daily report (the same text as `output/report.txt`), followed by:

```
Wrote 26 errors to ...\mission-log-parser\output\errors.txt
Wrote summary to ...\mission-log-parser\output\summary.json
Wrote report to ...\mission-log-parser\output\report.txt
```

## Log format

```
2026-03-01T04:12:09Z [ADCS] WARN reaction wheel 2 speed high
└──── timestamp ───┘ └subsys┘ └lvl┘ └──────── message ────────┘
```

| Field | Rule |
|---|---|
| Timestamp | ISO 8601 UTC, exactly `YYYY-MM-DDTHH:MM:SSZ`, and a real date and time |
| Subsystem | Inside square brackets, not empty |
| Level | One of `INFO`, `WARN`, `ERROR` |
| Message | Everything after the level; may contain spaces |

## Validation rules and malformed lines

Each line is split into at most four parts, then checked in this order. The first check that fails gives the reason.

| # | Check | Example rejected line | Reason reported |
|---|---|---|---|
| 1 | At least 4 fields | `2026-03-01T11:00:00Z [EPS] WARN` | `too few fields: expected 4, got 3` |
| 2 | Valid timestamp | `2026-13-45T25:00:00Z [OBC] INFO reboot complete` | `invalid timestamp ... '2026-13-45T25:00:00Z'` |
| 3 | Subsystem in brackets | `2026-03-01T06:00:00Z ADCS INFO mode change` | `invalid subsystem format: 'ADCS'` |
| 4 | Subsystem not empty | `2026-03-01T10:00:00Z [] INFO empty subsystem` | `subsystem must not be empty` |
| 5 | Known level | `2026-03-01T07:00:00Z [COMMS] DEBUGX signal check` | `invalid level ... 'DEBUGX'` |

The timestamp check parses the date with `datetime.strptime`, so it catches both a wrong format (`03/01/2026`) and impossible values (month 13, hour 25), not just the wrong shape.

## Sample input

`make_log.py` generates 490 valid lines with realistic proportions (about 80% INFO, 15% WARN, 5% ERROR) across six subsystems (ADCS, COMMS, EPS, OBC, PROP, THERMAL), plus one example of each of 10 malformed-line types inserted at random positions. The random seed is fixed, so the same file is produced every time; that is what makes the expected counts below exact.

## Results

### Counts

| | Count |
|---|---|
| Total lines | 500 |
| Valid | 490 |
| Malformed | 10 |
| INFO / WARN / ERROR | 388 / 76 / 26 |
| Time span | 2026-03-01 00:01:27 UTC to 21:44:31 UTC |

### Report excerpt (`output/report.txt`)

```
EVENTS BY SUBSYSTEM
  Subsystem   INFO  WARN  ERROR  Total
  ADCS          53    11      2     66
  COMMS         63    16      2     81
  EPS           63    13      7     83
  OBC           81    11      6     98
  PROP          67     9      1     77
  THERMAL       61    16      8     85
  Total        388    76     26    490
```

### Errors file excerpt (`output/errors.txt`)

```
2026-03-01T01:39:31Z [OBC] ERROR watchdog reset
2026-03-01T01:57:46Z [THERMAL] ERROR heater 2 stuck on
2026-03-01T03:38:26Z [OBC] ERROR watchdog reset
2026-03-01T04:46:18Z [OBC] ERROR command rejected: checksum error
2026-03-01T07:01:05Z [EPS] ERROR battery undervoltage
...
```

## Validation of the results

- **Totals reconcile:** valid + malformed = 500 lines in the file.
- **Rows and columns agree:** in the report, each subsystem row sums to its total, and the Total row (388 / 76 / 26 / 490) equals the level counts. The Total row is computed from the table, not typed, so a counting error would show up as a mismatch.
- **Round trip:** each line in `errors.txt` is rebuilt from the parsed record, and is identical to the original ERROR line in the log, so parsing loses no information.
- **Manual spot-check:** every reported malformed line number was opened in the editor and confirmed to be the bad line.

## Tests

Run `pytest -v` from the repo root. **25 tests** cover:

| Group | Tests | What it checks |
|---|---|---|
| Parsing valid lines | 3 | Fields split correctly, the message keeps its spaces, the timestamp is a UTC `datetime`, the trailing newline is ignored |
| Malformed lines | 10 | Each of the 10 malformed-line types is rejected with the right reason |
| Reading the file | 2 | 490 valid and 10 malformed lines, at the expected line numbers |
| Counting | 5 | Level and subsystem counts against the known answer; a consistency check that the subsystem × level table sums back to both (holds for any log); EPS errors; time span |
| Output files | 5 | `errors.txt` is identical to the original ERROR lines; `summary.json` values; report Total row; the saved report matches the printed one |

The output tests write to a temporary folder (pytest's `tmp_path`), so running the tests never overwrites `output/`.

## Design

Each function does one job, and the pipeline passes clean records from one stage to the next:

```
ops_log.txt -> read_log (uses parse_log_line) -> count_events, time_span
            -> write_errors / write_summary / write_report (uses build_report)
```

Only `parse_log_line` knows the line format. Adapting the tool to a different ground system's log format (other separators, day-of-year timestamps, numeric severities, extra fields) means changing that one function; reading, counting and reporting stay the same. `build_report` returns the report as lines instead of writing it, so the console and the file show identical text and the tests can check it without touching the disk.

## Analysis: why structured logging matters at 3 a.m.


When every line has the same fields (time, subsystem, severity, message), an operator can ask precise questions of the log in seconds instead of reading it line by line. Two examples from this report:

1. **The noisiest subsystem is not the most troubled one.** OBC produces the most events (98), but THERMAL (8) and EPS (7) produce the most errors. With free text you would notice the volume and look at the wrong system. The subsystem × level table points straight at the right ones.
2. **Patterns appear when you filter by field.** Filtering `errors.txt` for EPS shows that 3 of its 7 errors happen in the last hour of the log (20:17, 20:25 and 21:01 UTC), a cluster worth investigating before the next pass. Filtering for THERMAL shows "heater 2 stuck on" recurring 5 times across the day, which points to a persistent fault rather than a one-off. Both take one filter on structured fields; in free text they would take a careful read of 500 lines.

Structured logs also make the parser itself trustworthy: a line that does not fit the format is rejected with a reason instead of silently miscounted.

## Limitations

- The input path is fixed (`data/ops_log.txt`); there is no command-line option yet.
- Only three levels are recognised. Real systems often add DEBUG, CRITICAL or numeric severity codes.
- The whole file is read into memory, which is fine for a daily log but not for streaming telemetry.
- Timestamps must be UTC with a `Z` suffix; other time zones or fractional seconds are rejected.
- The sample log is synthetic, so the patterns in the analysis come from the generator's random choices, not from a real spacecraft.
