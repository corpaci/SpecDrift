#!/usr/bin/env python3
"""Extract per-pair ATP hardness from the ETP vampire run into compact arrays.

The ETP repo ships `data/<date>-vampire.json.gz`: for every ordered pair of
equations it records the solver's verdict, the wall-clock seconds it took, and
which solver configuration produced it. That wall-clock time is the only
per-pair, machine-checked hardness signal the project publishes, so it is what
`build_implications.py` stratifies on.

The file is ~88 MB gzipped and holds ~22M records, so it is streamed with a
regex over a sliding buffer rather than parsed as JSON, and the result is cached
as two dense arrays indexed by `[(i-1) * N + (j-1)]` for `Equation i => j`:

  vampire_time.npy    float32   seconds the winning solver took (nan = absent)
  vampire_method.npy  uint8     escalation rank of that solver (255 = absent)
  vampire_value.npy   uint8     verdict: 0 refuted, 1 proved, 2 unknown (255 = absent)

Escalation rank orders the configurations by the budget they were given, so
`(rank, time)` is a total order on hardness: anything the 600 s configs had to
settle is harder than anything a 5 s config closed. The verdict is kept only so
selection can cross-check this 2025 solver run against the 2024 outcomes
snapshot the oracle matrix is built from, and drop any pair where they disagree.

Usage:
    python3 build_difficulty.py [path/to/vampire.json.gz]

Falls back to $ETP_VAMPIRE, then $ETP_ROOT/data/2025-08-11-vampire.json.gz.
"""
from __future__ import annotations

import gzip
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

N = 4694
HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "data"

# Solver configurations, ordered by the search budget they were handed. A pair
# only reaches a later configuration because every earlier one timed out on it.
METHOD_RANK = {
    "vmi500": 0,   # 5 s   finite-model builder
    "vsi500": 0,   # 5 s   saturation (casc mode)
    "vms60": 1,    # 60 s  finite-model builder
    "vms600": 2,   # 600 s finite-model builder
    "vss600": 2,   # 600 s saturation (casc mode)
}
ABSENT_RANK = 255

RECORD = re.compile(
    rb'"(\d+)_(\d+)": \{"value": (\d+), "time": ([0-9.eE+-]+), "method_id": "([a-z0-9]+)"'
)
CHUNK = 1 << 24
# Longest a single record can be; the sliding buffer keeps at least this much
# tail so no record is lost across a chunk boundary.
OVERLAP = 256


def resolve_source(argv: list[str]) -> Path:
    if argv:
        return Path(argv[0]).expanduser()
    env = os.environ.get("ETP_VAMPIRE")
    if env:
        return Path(env).expanduser()
    root = Path(os.environ.get("ETP_ROOT", "~/equational_theories")).expanduser()
    return root / "data" / "2025-08-11-vampire.json.gz"


def main(argv: list[str]) -> int:
    src = resolve_source(argv)
    if not src.exists():
        sys.exit(
            f"vampire data not found at {src}\n"
            "Download data/2025-08-11-vampire.json.gz from the equational_theories\n"
            "repo and pass its path, or set $ETP_VAMPIRE / $ETP_ROOT."
        )

    times = np.full(N * N, np.nan, dtype=np.float32)
    methods = np.full(N * N, ABSENT_RANK, dtype=np.uint8)
    values = np.full(N * N, ABSENT_RANK, dtype=np.uint8)
    rank_of = {k.encode(): v for k, v in METHOD_RANK.items()}

    started = time.time()
    found = 0
    unknown_methods: set[bytes] = set()

    with gzip.open(src, "rb") as fh:
        buf = b""
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            buf += chunk
            # Scan everything except the tail, which may hold a partial record.
            scan_to = max(0, len(buf) - OVERLAP)
            last = 0
            for m in RECORD.finditer(buf, 0, scan_to):
                i = int(m.group(1))
                j = int(m.group(2))
                if not (1 <= i <= N and 1 <= j <= N):
                    continue
                rank = rank_of.get(m.group(5))
                if rank is None:
                    unknown_methods.add(m.group(5))
                    continue
                idx = (i - 1) * N + (j - 1)
                times[idx] = float(m.group(4))
                methods[idx] = rank
                values[idx] = int(m.group(3))
                found += 1
                last = m.end()
            buf = buf[max(last, scan_to):]
        # Drain whatever is left in the buffer.
        for m in RECORD.finditer(buf):
            i, j = int(m.group(1)), int(m.group(2))
            if not (1 <= i <= N and 1 <= j <= N):
                continue
            rank = rank_of.get(m.group(5))
            if rank is None:
                unknown_methods.add(m.group(5))
                continue
            idx = (i - 1) * N + (j - 1)
            times[idx] = float(m.group(4))
            methods[idx] = rank
            values[idx] = int(m.group(3))
            found += 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(OUT_DIR / "vampire_time.npy", times)
    np.save(OUT_DIR / "vampire_method.npy", methods)
    np.save(OUT_DIR / "vampire_value.npy", values)

    covered = int(np.count_nonzero(methods != ABSENT_RANK))
    print(f"source:   {src}")
    print(f"records:  {found:,} parsed, {covered:,} distinct pairs ({covered / (N * N):.2%} of {N}x{N})")
    for rank in (0, 1, 2):
        n = int(np.count_nonzero(methods == rank))
        print(f"  escalation rank {rank}: {n:,} pairs")
    if unknown_methods:
        print(f"  WARNING unrecognised method ids: {sorted(m.decode() for m in unknown_methods)}")
    print(f"wrote:    {OUT_DIR / 'vampire_time.npy'} ({times.nbytes / 1e6:.0f} MB)")
    for verdict, name in ((0, "refuted"), (1, "proved"), (2, "unknown")):
        print(f"  verdict {verdict} ({name}): {int(np.count_nonzero(values == verdict)):,} pairs")
    print(f"          {OUT_DIR / 'vampire_method.npy'} ({methods.nbytes / 1e6:.0f} MB)")
    print(f"          {OUT_DIR / 'vampire_value.npy'} ({values.nbytes / 1e6:.0f} MB)")
    print(f"elapsed:  {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
