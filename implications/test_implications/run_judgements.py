#!/usr/bin/env python3
"""Ask a model to judge each implication, once per representation.

For every one of the 250 implications in `implications_rendered.json` and every
one of the six representations, one chat completion is sent asking the single
question the dataset was built around: does Law A imply Law B? The model's
verdict is scored against the ETP implication graph.

Design choices that the comparison depends on:

*One call per cell.* 250 x 6 x 3 models = 4500 completions. Temperature 0 and
no sampling, so a cell is a single deterministic draw rather than a mean over
draws -- the variance that matters here is across representations, not across
resamples of the same cell.

*Reasoning off everywhere.* All three models are asked not to think before
answering (`reasoning: {enabled: false}`). Leaving it on for whichever models
default to it would confound "bigger model" with "spent more tokens", and the
question is about representation, not budget. `--reasoning` overrides this.

*Short, fixed answer contract.* A brief justification then `ANSWER:` and
`CONFIDENCE:` lines. The justification keeps the model from answering purely
from surface pattern; the confidence gives the analysis a calibration axis for
free.

Transport, retries, parameter recovery, and pricing come from
`translate/nl/openrouter.py`, the same client the translation sweeps use.

Results stream to `results/<slug>.jsonl` as they arrive and `--resume` picks up
where a killed run stopped.

Usage:
    python3 run_judgements.py --model anthropic/claude-opus-4.5
    python3 run_judgements.py --all              # the three-model ladder
    python3 run_judgements.py --all --dry-run    # price it without calling
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "translate" / "nl"))

import openrouter  # noqa: E402  (path set above)

RENDERED = REPO / "implications" / "implications_rendered.json"
RESULTS_DIR = HERE / "results"

# The ladder under test: one small, one mid-tier, one frontier model, from three
# different labs so "size" is not entangled with one vendor's house style.
MODELS = [
    # `concurrency` is a per-model override: the Mistral endpoint rate-limits
    # hard above a handful of parallel requests, while the other two do not.
    {"tier": "small", "id": "mistralai/mistral-small-3.2-24b-instruct",
     "slug": "mistral-small-3.2-24b", "concurrency": 5},
    {"tier": "medium", "id": "google/gemini-2.5-flash",
     "slug": "gemini-2.5-flash", "concurrency": 12},
    {"tier": "large", "id": "anthropic/claude-opus-4.5",
     "slug": "claude-opus-4.5", "concurrency": 10},
]

SYSTEM_PROMPT = """You are an expert in universal algebra and equational logic.

You will be shown two equational laws, Law A and Law B, for a single binary \
operation on an arbitrary set. Decide whether Law A implies Law B: whether \
every binary operation satisfying Law A must also satisfy Law B.

Answer TRUE if the implication holds for every binary operation on every set.
Answer FALSE if some binary operation on some set satisfies Law A but not Law B.

Be brief. Use at most 60 words of justification. Do not enumerate cases \
exhaustively and do not verify a candidate operation element by element -- if a \
counterexample exists, name the operation and stop. Then end your reply with \
exactly these two lines and nothing after them:

ANSWER: TRUE or FALSE
CONFIDENCE: an integer from 50 to 100"""

MAX_TOKENS = 900
TEMPERATURE = 0.0

ANSWER_RE = re.compile(r"ANSWER\s*[:\-]?\s*\**\s*(TRUE|FALSE)\b", re.IGNORECASE)
CONFIDENCE_RE = re.compile(r"CONFIDENCE\s*[:\-]?\s*\**\s*(\d{1,3})", re.IGNORECASE)
# Last-resort scan, used only when the contract line is missing entirely.
BARE_RE = re.compile(r"\b(TRUE|FALSE)\b", re.IGNORECASE)


def parse_verdict(text: str) -> tuple[str | None, int | None, str]:
    """Pull `(verdict, confidence, how_it_was_read)` out of a completion.

    The contract line is tried first. A model that ignored the format but still
    committed to a word is read from its *last* TRUE/FALSE, which is where a
    verdict lands when one is stated at all; anything else is left unparsed
    rather than guessed, and shows up in the analysis as its own outcome.
    """
    if not text:
        return None, None, "empty"
    confidence = None
    if (m := CONFIDENCE_RE.search(text)) is not None:
        value = int(m.group(1))
        confidence = value if 0 <= value <= 100 else None
    matches = ANSWER_RE.findall(text)
    if matches:
        return matches[-1].lower(), confidence, "contract"
    bare = BARE_RE.findall(text)
    if bare:
        return bare[-1].lower(), confidence, "scanned"
    return None, confidence, "unparsed"


def load_tasks(representations: list[str] | None, limit: int | None) -> tuple[list[dict], dict]:
    if not RENDERED.exists():
        sys.exit(f"missing {RENDERED}\nrun `implications/build_representations.py` first")
    payload = json.loads(RENDERED.read_text(encoding="utf-8"))
    reps = representations or payload["meta"]["representations"]
    unknown = set(reps) - set(payload["meta"]["representations"])
    if unknown:
        sys.exit(f"unknown representation(s): {sorted(unknown)}")

    records = payload["implications"]
    if limit:
        # Keep the class/difficulty mix of a smoke test representative rather
        # than taking the first N, which are sorted and would be all one cell.
        step = max(1, len(records) // limit)
        records = records[::step][:limit]

    tasks = []
    for rec in records:
        for rep in reps:
            tasks.append(
                {
                    "id": rec["id"],
                    "representation": rep,
                    "prompt": rec["representations"][rep]["prompt"],
                    "label": rec["label"],
                    "difficulty": rec["difficulty"],
                    "hypothesis": rec["hypothesis"],
                    "conclusion": rec["conclusion"],
                }
            )
    return tasks, payload["meta"]


def identity_of(model: dict, reps: list[str], dataset_meta: dict, max_tokens: int) -> dict:
    """What a checkpoint must match before a resume is allowed."""
    return {
        "model": model["id"],
        "system_sha": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:12],
        "dataset_seed": dataset_meta.get("seed"),
        "dataset_count": dataset_meta.get("count"),
        "representations": sorted(reps),
        "max_tokens": max_tokens,
        "temperature": TEMPERATURE,
    }


def load_checkpoint(path: Path, identity: dict) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    done: dict[tuple[str, str], dict] = {}
    with path.open(encoding="utf-8") as fh:
        header = fh.readline()
        try:
            stored = json.loads(header)["identity"]
        except (json.JSONDecodeError, KeyError):
            sys.exit(f"{path}: unreadable checkpoint header; delete it to start over")
        if stored != identity:
            sys.exit(
                f"{path}: checkpoint was written for a different run.\n"
                f"  stored: {json.dumps(stored, sort_keys=True)}\n"
                f"  wanted: {json.dumps(identity, sort_keys=True)}\n"
                "Delete it, or pass a different --results-dir, to start over."
            )
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # a torn final line from a killed run
            done[(row["id"], row["representation"])] = row
    return done


def run_model(
    model: dict,
    tasks: list[dict],
    dataset_meta: dict,
    *,
    client,
    concurrency: int,
    resume: bool,
    reasoning: bool,
    results_dir: Path,
    max_tokens: int,
) -> dict:
    reps = sorted({t["representation"] for t in tasks})
    identity = identity_of(model, reps, dataset_meta, max_tokens)
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"{model['slug']}.jsonl"

    done = load_checkpoint(path, identity) if resume else {}
    if not resume and path.exists():
        path.unlink()
    pending = [t for t in tasks if (t["id"], t["representation"]) not in done]

    print(
        f"[{model['tier']:6s}] {model['id']}: {len(pending)} calls"
        + (f" ({len(done)} resumed)" if done else "")
    )
    if not pending:
        return {"model": model, "rows": list(done.values()), "elapsed": 0.0}

    handle = path.open("a" if done else "w", encoding="utf-8")
    if not done:
        handle.write(json.dumps({"identity": identity, "started_at": _now()}) + "\n")
        handle.flush()

    lock = threading.Lock()
    rows = list(done.values())
    counters = {"ok": 0, "error": 0, "unparsed": 0, "truncated": 0, "cost": 0.0}
    started = time.time()

    def one(task: dict) -> None:
        payload = {
            "model": model["id"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task["prompt"]},
            ],
            "max_tokens": max_tokens,
            "temperature": TEMPERATURE,
            "usage": {"include": True},
        }
        if not reasoning:
            payload["reasoning"] = {"enabled": False}

        row = {
            "id": task["id"],
            "representation": task["representation"],
            "model": model["id"],
            "tier": model["tier"],
            "label": task["label"],
            "difficulty": task["difficulty"],
            "hypothesis": task["hypothesis"],
            "conclusion": task["conclusion"],
            "timestamp": _now(),
        }
        call_started = time.time()
        try:
            body, dropped, attempts = _send_with_backoff(client, payload)
        except Exception as exc:  # recorded, not raised: one dead cell is data
            row |= {
                "status": "error",
                "error": openrouter._snip(f"{type(exc).__name__}: {exc}"),
                "latency_s": round(time.time() - call_started, 3),
            }
        else:
            choice = (body.get("choices") or [{}])[0]
            text = ((choice.get("message") or {}).get("content") or "").strip()
            verdict, confidence, how = parse_verdict(text)
            usage = body.get("usage") or {}
            truncated = choice.get("finish_reason") == "length"
            row |= {
                "status": "ok" if verdict else ("truncated" if truncated else "unparsed"),
                "response": text,
                "verdict": verdict,
                "correct": None if verdict is None else (verdict == task["label"]),
                "confidence": confidence,
                "extraction": how,
                "finish_reason": choice.get("finish_reason"),
                "upstream_provider": body.get("provider"),
                "usage": {
                    "input_tokens": usage.get("prompt_tokens"),
                    "output_tokens": usage.get("completion_tokens"),
                    "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get(
                        "reasoning_tokens"
                    ),
                    "cost_usd": usage.get("cost"),
                },
                "dropped_params": dropped or None,
                "attempts": attempts,
                "latency_s": round(time.time() - call_started, 3),
            }

        with lock:
            rows.append(row)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()  # a killed run loses at most the in-flight calls
            counters[row["status"] if row["status"] in counters else "ok"] += 1
            counters["cost"] += (row.get("usage") or {}).get("cost_usd") or 0.0
            n = len(rows)
            if n % 100 == 0 or n == len(tasks):
                rate = n / max(1e-9, time.time() - started)
                print(
                    f"  [{model['slug']}] {n}/{len(tasks)}  "
                    f"ok={counters['ok']} trunc={counters['truncated']} "
                    f"unparsed={counters['unparsed']} err={counters['error']}  "
                    f"${counters['cost']:.3f}  "
                    f"{rate:.1f}/s",
                    flush=True,
                )

    try:
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            list(pool.map(one, pending))
    finally:
        handle.close()

    return {"model": model, "rows": rows, "elapsed": time.time() - started}


# Statuses worth waiting out. The SDK already retries these, but its budget is
# spent quickly when a whole pool of workers hits one provider's rate limit at
# once, so the run adds a slower outer loop on top.
TRANSIENT = frozenset({408, 409, 429, 500, 502, 503, 504})
BACKOFF_ATTEMPTS = 5
BACKOFF_BASE_S = 4.0


def _send_with_backoff(client, payload: dict):
    """`call_with_recovery`, plus an outer wait-and-retry on transient errors."""
    last: Exception | None = None
    for attempt in range(BACKOFF_ATTEMPTS):
        try:
            return openrouter.call_with_recovery(
                lambda p: openrouter.chat(client, p)[0], payload
            )
        except openrouter.OpenRouterError as exc:
            if exc.status not in TRANSIENT:
                raise
            last = exc
            if attempt < BACKOFF_ATTEMPTS - 1:
                # Deterministic-ish backoff with a jitter drawn from the worker
                # identity, so a pool released together does not re-collide.
                jitter = (threading.get_ident() % 1000) / 1000.0
                time.sleep(BACKOFF_BASE_S * (2 ** attempt) * (0.5 + jitter))
    raise last  # type: ignore[misc]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def report_status(models: list[dict], tasks: list[dict], results_dir: Path) -> None:
    """Print what each model has finished, without touching the network.

    Reads the checkpoints the way a resume would, so `--status` answers the
    only question that matters after an interrupted run: how much is left, and
    is the checkpoint still usable.
    """
    wanted = {(t["id"], t["representation"]) for t in tasks}
    print(f"{results_dir}  ({len(wanted)} cells per model)\n")
    for model in models:
        path = results_dir / f"{model['slug']}.jsonl"
        if not path.exists():
            print(f"  {model['tier']:6s} {model['slug']:24s} not started")
            continue
        rows, torn = [], 0
        with path.open(encoding="utf-8") as fh:
            fh.readline()  # identity header
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    torn += 1
        done = {(r["id"], r["representation"]) for r in rows}
        scored = [r for r in rows if r.get("correct") is not None]
        acc = sum(r["correct"] for r in scored) / len(scored) if scored else 0.0
        cost = sum((r.get("usage") or {}).get("cost_usd") or 0.0 for r in rows)
        errs = sum(1 for r in rows if r.get("status") == "error")
        print(
            f"  {model['tier']:6s} {model['slug']:24s} "
            f"{len(done & wanted):4d}/{len(wanted)} done  "
            f"{len(wanted - done):4d} left  "
            f"acc {acc:5.1%}  err {errs:3d}  ${cost:6.3f}"
            + (f"  ({torn} torn line(s), will be re-run)" if torn else "")
        )


def estimate(models: list[dict], tasks: list[dict]) -> None:
    """Price the sweep from the live catalogue before spending anything."""
    catalogue = openrouter.catalogue()
    catalogue.load()
    # ~4 chars per token is close enough for the small, ASCII-heavy prompts here.
    in_tokens = sum(len(t["prompt"]) for t in tasks) / 4 + len(tasks) * len(SYSTEM_PROMPT) / 4
    out_tokens = len(tasks) * 200  # observed: a 60-word justification plus 2 lines
    total = 0.0
    print(f"{len(tasks)} prompts per model; ~{in_tokens/1e3:.0f}k in, ~{out_tokens/1e3:.0f}k out\n")
    for model in models:
        price = catalogue.price(model["id"])
        if price is None:
            print(f"  {model['id']:48s} not in catalogue")
            continue
        cost = in_tokens * price[0] + out_tokens * price[1]
        total += cost
        print(
            f"  {model['tier']:6s} {model['id']:48s} "
            f"${price[0]*1e6:7.3f}/M in  ${price[1]*1e6:7.3f}/M out  -> ${cost:6.2f}"
        )
    print(f"\n  {'total':6s} {'':48s} {'':32s} -> ${total:6.2f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", action="append", help="OpenRouter model id (repeatable)")
    ap.add_argument("--all", action="store_true", help="run the three-model ladder")
    ap.add_argument("--representation", action="append", help="restrict to these (repeatable)")
    ap.add_argument("--limit", type=int, help="use only N implications (smoke test)")
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    ap.add_argument("--concurrency", type=int, default=0,
                    help="override the per-model default")
    ap.add_argument("--resume", action="store_true", help="continue from results/<slug>.jsonl")
    ap.add_argument("--reasoning", action="store_true", help="do NOT disable model reasoning")
    ap.add_argument("--dry-run", action="store_true", help="price the sweep and exit")
    ap.add_argument("--status", action="store_true",
                    help="report checkpoint progress and exit; makes no calls")
    ap.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = ap.parse_args()

    tasks, dataset_meta = load_tasks(args.representation, args.limit)

    if args.model:
        known = {m["id"]: m for m in MODELS}
        models = [
            known.get(mid, {"tier": "custom", "id": mid, "slug": mid.replace("/", "--")})
            for mid in args.model
        ]
    elif args.all:
        models = MODELS
    else:
        ap.error("pass --all or at least one --model")

    if args.status:
        report_status(models, tasks, args.results_dir)
        return 0

    if args.dry_run:
        estimate(models, tasks)
        return 0

    key = openrouter.load_api_key(os.environ.get("OPENROUTER_API_KEY"))
    client = openrouter.make_client(key, timeout=180.0, max_retries=4)

    print(f"{len(tasks)} prompts x {len(models)} model(s) = {len(tasks)*len(models)} calls")
    print(f"reasoning: {'model default' if args.reasoning else 'disabled'}\n")

    started = time.time()
    summaries = []
    for model in models:
        result = run_model(
            model,
            tasks,
            dataset_meta,
            client=client,
            concurrency=args.concurrency or model.get("concurrency", 8),
            resume=args.resume,
            reasoning=args.reasoning,
            results_dir=args.results_dir,
            max_tokens=args.max_tokens,
        )
        rows = result["rows"]
        scored = [r for r in rows if r.get("correct") is not None]
        cost = sum((r.get("usage") or {}).get("cost_usd") or 0.0 for r in rows)
        accuracy = sum(r["correct"] for r in scored) / len(scored) if scored else 0.0
        summaries.append(
            {
                "model": model["id"],
                "tier": model["tier"],
                "slug": model["slug"],
                "rows": len(rows),
                "scored": len(scored),
                "errors": sum(1 for r in rows if r["status"] == "error"),
                "unparsed": sum(1 for r in rows if r["status"] == "unparsed"),
                "truncated": sum(1 for r in rows if r["status"] == "truncated"),
                "accuracy": round(accuracy, 4),
                "cost_usd": round(cost, 4),
                "elapsed_s": round(result["elapsed"], 1),
            }
        )
        print(
            f"  -> {model['slug']}: accuracy {accuracy:.1%} over {len(scored)} scored, "
            f"${cost:.3f}, {result['elapsed']/60:.1f} min\n"
        )

    manifest = {
        "generator": "implications/test_implications/run_judgements.py",
        "finished_at": _now(),
        "elapsed_s": round(time.time() - started, 1),
        "system_prompt": SYSTEM_PROMPT,
        "max_tokens": args.max_tokens,
        "temperature": TEMPERATURE,
        "reasoning_disabled": not args.reasoning,
        "dataset": {k: dataset_meta.get(k) for k in ("seed", "count", "representations")},
        "sdk": f"openai {openrouter.sdk_version()} via OpenRouter",
        "models": summaries,
        "total_cost_usd": round(sum(s["cost_usd"] for s in summaries), 4),
    }
    # One process per model is the normal way to run this (they are independent
    # and the small model is much the slowest), so a single-model run gets its
    # own manifest rather than racing the others for a shared filename.
    manifest_name = (
        f"manifest-{models[0]['slug']}.json" if len(models) == 1 else "manifest.json"
    )
    (args.results_dir / manifest_name).write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(f"total ${manifest['total_cost_usd']:.3f} in {manifest['elapsed_s']/60:.1f} min")
    print(f"wrote {args.results_dir / manifest_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
