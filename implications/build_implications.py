#!/usr/bin/env python3
"""Select a diverse, difficulty-stratified benchmark of 250 ETP implications.

Produces `implications.json`: 250 ordered pairs (A, B) of ETP equations, each
labelled with the ground-truth status of `A => B` and a difficulty tier.

Ground truth
------------
Taken from the project's own oracle matrix (`oracle/data/matrix.bin`, built from
the 2024-11-10 ETP outcomes snapshot). Only the two *proven* statuses are
eligible -- `proof_true` and `proof_false`. Conjectures and the handful of still
-open pairs are excluded, so every label is machine-checked.

As a second guard, each pair's label is cross-checked against the independent
2025-08-11 Vampire run (`build_difficulty.py`). Pairs where the two sources
disagree are dropped (917 of them, ~0.004%).

Difficulty
----------
The Vampire run records, per pair, the wall-clock seconds the winning solver
configuration needed. That is the only per-pair, machine-measured hardness
signal ETP publishes, and it is the primary axis here. It is paired with a
syntactic axis -- `order(A) + order(B)`, the combined count of operation
symbols -- because a law's surface complexity is what a reader (or a model)
actually has to hold in its head.

Terciles of these would be meaningless: 99.8% of pairs are solved in under
0.1 s, so the mass of the distribution carries almost no signal. Instead the
tiers are *absolute bands* chosen to separate:

    tier    ATP seconds (within-class pctile)   order(A)+order(B)
    easy    <= 25th                             <= 4
    medium  40th .. 60th                        6 .. 7
    hard    >= 0.1 s (~top 0.13% of the class)  >= 7

The bands are deliberately non-exhaustive -- the gaps between them are what
makes the tiers contrast. Measured separation on the resulting pools:

    true   easy  8 ms / order-sum 3.9   medium 23 ms / 6.9   hard 248 ms / 7.9
    false  easy  5 ms / order-sum 4.0   medium  7 ms / 6.9   hard 1.92 s / 7.9

Diversity
---------
Within a stratum, candidates are bucketed by their `(order(A), order(B))` shape
and drawn round-robin across buckets, so no stratum collapses onto one shape.
A global cap of MAX_NODE_USES appearances per equation (counting both sides,
across all 250) stops the sample concentrating on hub laws -- ETP's hard proven
implications in particular are dominated by equations 650 and 2923, which
without the cap would appear in most of the hard-true tier.

Equations 1 (`x = x`) and 2 (`x = y`) are excluded outright: the first is
implied by every law and the second implies every law, so pairs involving them
are artefacts of the lattice's top and bottom rather than real reasoning.
Equations whose natural-language description failed to generate, came back
empty, or leaked notation are also excluded, so that every selected pair is
renderable in all six representations.

Usage:
    python3 build_implications.py [--seed N] [--out PATH]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
N = 4694

MATRIX_BIN = REPO / "oracle" / "data" / "matrix.bin"
LATEX_JSON = REPO / "translate" / "latex" / "etp_equations_latex.json"
NL_JSON = REPO / "translate" / "nl" / "descriptions-qwen3.json"
DATA_DIR = HERE / "data"

# Byte values in matrix.bin (oracle/build_matrix.py STATUS_NAMES).
PROOF_FALSE, PROOF_TRUE = 0, 1

# Degenerate top/bottom of the implication lattice.
EXCLUDED_NODES = frozenset({1, 2})

# Max times any one equation may appear across the whole benchmark (either side).
MAX_NODE_USES = 4

# Tier bands: (atp-percentile lo, hi, order-sum lo, hi). `None` = unbounded.
# The hard band uses an absolute second threshold rather than a percentile,
# because the percentile that isolates it differs between the two classes.
TIER_BANDS = {
    "easy": dict(pctile=(0.0, 0.25), abs_seconds=None, order_sum=(0, 4)),
    "medium": dict(pctile=(0.40, 0.60), abs_seconds=None, order_sum=(6, 7)),
    "hard": dict(pctile=None, abs_seconds=(0.1, None), order_sum=(7, None)),
}

# 125 per class, split as evenly as 3 divides 125. The odd item goes to a
# different tier in each class so the tier totals also come out near-even
# (easy 83, medium 84, hard 83).
QUOTAS = {
    (PROOF_TRUE, "easy"): 42,
    (PROOF_TRUE, "medium"): 42,
    (PROOF_TRUE, "hard"): 41,
    (PROOF_FALSE, "easy"): 41,
    (PROOF_FALSE, "medium"): 42,
    (PROOF_FALSE, "hard"): 42,
}


def load_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict]:
    """Return (status, atp_time, atp_rank, atp_value, order, formal_by_node)."""
    for path in (MATRIX_BIN, LATEX_JSON, NL_JSON):
        if not path.exists():
            sys.exit(f"missing input: {path}")
    for name in ("vampire_time.npy", "vampire_method.npy", "vampire_value.npy"):
        if not (DATA_DIR / name).exists():
            sys.exit(f"missing {DATA_DIR / name}\nrun `python3 build_difficulty.py` first")

    status = np.fromfile(MATRIX_BIN, dtype=np.uint8).reshape(N, N)
    atp_time = np.load(DATA_DIR / "vampire_time.npy").reshape(N, N)
    atp_rank = np.load(DATA_DIR / "vampire_method.npy").reshape(N, N)
    atp_value = np.load(DATA_DIR / "vampire_value.npy").reshape(N, N)

    equations = json.loads(LATEX_JSON.read_text(encoding="utf-8"))["equations"]
    order = np.array([e["order"] for e in equations], dtype=np.int16)
    formal = {e["node"]: e["formal"] for e in equations}
    return status, atp_time, atp_rank, atp_value, order, formal


def usable_nodes() -> np.ndarray:
    """Boolean mask over 0-based node indices: renderable in all six forms."""
    descriptions = json.loads(NL_JSON.read_text(encoding="utf-8"))["descriptions"]
    ok = np.zeros(N, dtype=bool)
    for row in descriptions:
        if (
            row.get("status") == "ok"
            and row.get("description")
            and not row.get("mentions_notation")
        ):
            ok[row["node"] - 1] = True
    for node in EXCLUDED_NODES:
        ok[node - 1] = False
    return ok


def candidate_mask(status, atp_rank, atp_value, node_ok) -> np.ndarray:
    """Pairs eligible for selection: proven, cross-checked, fully renderable."""
    mask = np.outer(node_ok, node_ok)
    np.fill_diagonal(mask, False)
    proven = (status == PROOF_TRUE) | (status == PROOF_FALSE)
    # Vampire's verdict enum happens to agree with the matrix byte values for
    # the two proven statuses (0 refuted / 1 proved), so this is a direct match.
    agrees = ((status == PROOF_TRUE) & (atp_value == 1)) | (
        (status == PROOF_FALSE) & (atp_value == 0)
    )
    covered = atp_rank != 255
    return mask & proven & agrees & covered


def band_mask(pool, atp_time, order_sum, band) -> np.ndarray:
    """Apply one tier band to a within-class candidate pool."""
    sel = pool.copy()
    if band["pctile"] is not None:
        lo, hi = np.quantile(atp_time[pool], band["pctile"])
        sel &= (atp_time >= lo) & (atp_time <= hi)
    if band["abs_seconds"] is not None:
        lo, hi = band["abs_seconds"]
        if lo is not None:
            sel &= atp_time >= lo
        if hi is not None:
            sel &= atp_time <= hi
    lo, hi = band["order_sum"]
    if lo is not None:
        sel &= order_sum >= lo
    if hi is not None:
        sel &= order_sum <= hi
    return sel


def draw(sel, order, quota, rng, node_uses, taken) -> list[tuple[int, int]]:
    """Pick `quota` pairs from `sel`, round-robin across (order, order) shapes.

    Shuffling alone would let a stratum collapse onto whichever shape dominates
    it (order-4 vs order-4, overwhelmingly). Bucketing by shape and cycling the
    buckets spreads the draw across every shape the stratum actually offers.
    """
    rows, cols = np.nonzero(sel)
    if len(rows) == 0:
        return []
    perm = rng.permutation(len(rows))
    buckets: dict[tuple[int, int], collections.deque] = collections.defaultdict(
        collections.deque
    )
    for k in perm:
        a, b = int(rows[k]) + 1, int(cols[k]) + 1
        buckets[(int(order[a - 1]), int(order[b - 1]))].append((a, b))

    shapes = sorted(buckets)
    rng.shuffle(shapes)
    picked: list[tuple[int, int]] = []
    # Cycle the shapes, taking the next admissible pair from each in turn, until
    # the quota is met or every bucket is exhausted.
    while len(picked) < quota and shapes:
        progressed = False
        for shape in list(shapes):
            if len(picked) >= quota:
                break
            queue = buckets[shape]
            while queue:
                a, b = queue.popleft()
                if (a, b) in taken or (b, a) in taken:
                    continue
                if node_uses[a] >= MAX_NODE_USES or node_uses[b] >= MAX_NODE_USES:
                    continue
                node_uses[a] += 1
                node_uses[b] += 1
                taken.add((a, b))
                picked.append((a, b))
                progressed = True
                break
            if not queue:
                shapes.remove(shape)
        if not progressed:
            break
    return picked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--out", type=Path, default=HERE / "implications.json")
    args = ap.parse_args()

    status, atp_time, atp_rank, atp_value, order, formal = load_inputs()
    node_ok = usable_nodes()
    candidates = candidate_mask(status, atp_rank, atp_value, node_ok)
    order_sum = (order[:, None] + order[None, :]).astype(np.int16)

    print(f"usable equations:  {int(node_ok.sum())} / {N}")
    print(f"candidate pairs:   {int(candidates.sum()):,}")

    rng = np.random.default_rng(args.seed)
    node_uses: collections.Counter[int] = collections.Counter()
    taken: set[tuple[int, int]] = set()
    records = []

    # Draw the scarcest strata first: the easy tiers come from only ~400
    # low-order equations, so they must claim their node budget before the
    # medium tiers (which can draw from all 4600) start consuming it.
    stratum_order = [
        (cls, tier)
        for tier in ("easy", "hard", "medium")
        for cls in (PROOF_TRUE, PROOF_FALSE)
    ]

    for cls, tier in stratum_order:
        pool = candidates & (status == cls)
        sel = band_mask(pool, atp_time, order_sum, TIER_BANDS[tier])
        quota = QUOTAS[(cls, tier)]
        picked = draw(sel, order, quota, rng, node_uses, taken)
        label = "true" if cls == PROOF_TRUE else "false"
        if len(picked) < quota:
            sys.exit(
                f"stratum ({label}, {tier}) yielded {len(picked)} of {quota} pairs; "
                "loosen MAX_NODE_USES or widen the band"
            )
        for a, b in picked:
            i, j = a - 1, b - 1
            records.append(
                {
                    "id": None,  # assigned after the global sort below
                    "hypothesis": a,
                    "conclusion": b,
                    "hypothesis_formal": formal[a],
                    "conclusion_formal": formal[b],
                    "label": label,
                    "matrix_status": "proof_true" if cls == PROOF_TRUE else "proof_false",
                    "difficulty": tier,
                    "atp_seconds": round(float(atp_time[i, j]), 6),
                    "atp_escalation_rank": int(atp_rank[i, j]),
                    "hypothesis_order": int(order[i]),
                    "conclusion_order": int(order[j]),
                    "order_sum": int(order_sum[i, j]),
                }
            )
        print(
            f"  {label:5s} {tier:6s}: {len(picked):3d} pairs   "
            f"median ATP {np.median([r['atp_seconds'] for r in records[-len(picked):]]):.4f}s   "
            f"mean order-sum {np.mean([r['order_sum'] for r in records[-len(picked):]]):.2f}"
        )

    records.sort(key=lambda r: (r["label"], r["difficulty"], r["hypothesis"], r["conclusion"]))
    for n, rec in enumerate(records, 1):
        rec["id"] = f"impl-{n:03d}"

    counts = collections.Counter((r["label"], r["difficulty"]) for r in records)
    payload = {
        "meta": {
            "generator": "implications/build_implications.py",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "seed": args.seed,
            "count": len(records),
            "ground_truth": {
                "source": "oracle/data/matrix.bin (ETP 2024-11-10 outcomes)",
                "eligible_statuses": ["proof_true", "proof_false"],
                "crosscheck": "ETP 2025-08-11 Vampire run; disagreeing pairs dropped",
            },
            "difficulty": {
                "primary_signal": "Vampire wall-clock seconds for the pair",
                "secondary_signal": "order(A) + order(B)",
                "bands": TIER_BANDS,
            },
            "diversity": {
                "max_node_uses": MAX_NODE_USES,
                "excluded_nodes": sorted(EXCLUDED_NODES),
                "distinct_equations": len(node_uses),
                "round_robin": "(order(A), order(B)) shape buckets",
            },
            "counts": {f"{k[0]}/{k[1]}": v for k, v in sorted(counts.items())},
        },
        "implications": records,
    }
    args.out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"\ndistinct equations used: {len(node_uses)} (max uses {max(node_uses.values())})")
    print(f"wrote {args.out} ({len(records)} implications)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
