"""Generate a sample spacecraft operations log for the parser to read.

Writes data/ops_log.txt: about 500 lines of the form
    2026-03-01T04:12:09Z [ADCS] WARN reaction wheel 2 speed high
plus 10 deliberately malformed lines scattered through the file.

The random seed is fixed, so the same file is produced on every run.
Run:  py make_log.py
"""
import os
import random
from datetime import datetime, timedelta, timezone

SEED = 42
N_VALID = 490
START = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
STEP_SECONDS = (30, 300)          # random gap between lines

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "ops_log.txt")

LEVELS = ["INFO", "WARN", "ERROR"]
LEVEL_WEIGHTS = [80, 15, 5]       # about 80% INFO, 15% WARN, 5% ERROR

MESSAGES = {
    "ADCS": {
        "INFO": ["attitude nominal", "sun sensor update received", "star tracker lock acquired"],
        "WARN": ["reaction wheel 2 speed high", "pointing error above 0.1 deg"],
        "ERROR": ["star tracker lock lost", "reaction wheel 2 overspeed fault"],
    },
    "EPS": {
        "INFO": ["battery charge nominal", "solar array current nominal", "bus voltage 28.1 V"],
        "WARN": ["battery temperature approaching limit", "bus voltage low 26.4 V"],
        "ERROR": ["battery undervoltage", "solar array string 3 open circuit"],
    },
    "COMMS": {
        "INFO": ["downlink session started", "downlink session complete", "carrier lock acquired"],
        "WARN": ["signal strength below threshold", "packet retransmissions high"],
        "ERROR": ["uplink lock lost", "transponder reset"],
    },
    "THERMAL": {
        "INFO": ["temperatures nominal", "heater 1 on", "heater 1 off"],
        "WARN": ["payload temperature high", "radiator temperature low"],
        "ERROR": ["payload over-temperature", "heater 2 stuck on"],
    },
    "OBC": {
        "INFO": ["housekeeping cycle complete", "command accepted", "time sync complete"],
        "WARN": ["memory usage above 80%", "watchdog near timeout"],
        "ERROR": ["watchdog reset", "command rejected: checksum error"],
    },
    "PROP": {
        "INFO": ["tank pressure nominal", "valve 1 closed", "thruster warm-up complete"],
        "WARN": ["tank pressure drifting low", "thruster 3 temperature high"],
        "ERROR": ["valve 2 failed to open", "thruster 3 underperformance"],
    },
}

# One example of each kind of bad line (the parser must skip all of these)
MALFORMED = [
    "",                                                     # blank line
    "2026-03-01T05:00:00Z [EPS] battery nominal",           # missing level
    "2026-13-45T25:00:00Z [OBC] INFO reboot complete",      # impossible timestamp
    "2026-03-01T06:00:00Z ADCS INFO mode change",           # missing brackets
    "2026-03-01T07:00:00Z [COMMS] DEBUGX signal check",     # unknown level
    "2026-03-01T08:00:00Z [PRO",                            # truncated line
    "03/01/2026 09:00 [THERMAL] INFO heater 1 on",          # wrong timestamp format
    "2026-03-01T10:00:00Z [] INFO empty subsystem",         # empty subsystem
    "2026-03-01T11:00:00Z [EPS] WARN",                      # no message
    "garbage line with no structure",                       # free text
]


def make_valid_lines(rng):
    """Return N_VALID log lines with increasing timestamps."""
    lines = []
    t = START
    for _ in range(N_VALID):
        t += timedelta(seconds=rng.randint(*STEP_SECONDS))
        subsystem = rng.choice(list(MESSAGES))
        level = rng.choices(LEVELS, weights=LEVEL_WEIGHTS)[0]
        message = rng.choice(MESSAGES[subsystem][level])
        lines.append(f"{t:%Y-%m-%dT%H:%M:%SZ} [{subsystem}] {level} {message}")
    return lines


def insert_malformed(lines, rng):
    """Insert each malformed line at a random position (never first or last)."""
    result = list(lines)
    for bad in MALFORMED:
        result.insert(rng.randint(1, len(result) - 1), bad)
    return result


def main():
    rng = random.Random(SEED)
    lines = insert_malformed(make_valid_lines(rng), rng)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {len(lines)} lines ({N_VALID} valid, {len(MALFORMED)} malformed) to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()