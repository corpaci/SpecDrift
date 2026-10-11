#!/usr/bin/env python3
"""Render each selected implication into all six representations.

Reads `implications.json` (from `build_implications.py`) and emits
`implications_rendered.json`, which carries, for every implication and every
representation, the exact user prompt that will be sent to a model.

The six representations all come from `translate/`:

    etp         the catalogue's own form,    x = x ◇ y
    latex       translate/latex              x = x \\diamond y
    lean        translate/lean               Lean 4 `Prop`s over a `Magma` class
    nl          translate/nl                 English prose (Qwen3-30B-A3B)
    py_lambda   translate/py_lambda          a predicate over `op` and elements
    py_cayley   translate/py_cayley_table    a checker over a finite Cayley table

Two properties matter for the experiment to measure what it claims to:

*No node leakage.* An ETP equation number anywhere in a prompt would let a model
retrieve the answer instead of reasoning about it. Nothing rendered here carries
one, and `--check` asserts it.

*One semantic target.* The ground-truth labels are about arbitrary magmas,
finite or infinite. Every framing therefore says so explicitly -- including the
Cayley-table one, whose checker is necessarily finite but whose *law* is not.
Without that clause the Python-table condition would be asking a subtly
different question from the other five.

Usage:
    python3 build_representations.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TRANSLATE = REPO / "translate"

SOURCES = {
    "etp": (TRANSLATE / "latex" / "etp_equations_latex.json", "formal"),
    "latex": (TRANSLATE / "latex" / "etp_equations_latex.json", "latex"),
    "lean": (TRANSLATE / "lean" / "etp_equations_lean.json", "statement"),
    "py_lambda": (TRANSLATE / "py_lambda" / "etp_equations_py_lambda.json", "py_lambda"),
    "py_cayley": (
        TRANSLATE / "py_cayley_table" / "etp_equations_py_cayley_table.json",
        "py_cayley_table",
    ),
}
NL_JSON = TRANSLATE / "nl" / "descriptions-qwen3.json"

REPRESENTATIONS = ("etp", "latex", "lean", "nl", "py_lambda", "py_cayley")

# The question is identical in all six; only the medium changes.
QUESTION = (
    "Does Law A imply Law B? That is: must every binary operation that "
    "satisfies Law A also satisfy Law B?"
)
SCOPE = (
    "The operation ranges over an arbitrary set, which may be finite or "
    "infinite, and the laws are universally quantified over all values of "
    "their variables."
)


def load_catalogues() -> dict[str, dict[int, str]]:
    out: dict[str, dict[int, str]] = {}
    for name, (path, field) in SOURCES.items():
        if not path.exists():
            sys.exit(f"missing catalogue: {path}")
        rows = json.loads(path.read_text(encoding="utf-8"))["equations"]
        out[name] = {r["node"]: r[field] for r in rows}
    if not NL_JSON.exists():
        sys.exit(f"missing catalogue: {NL_JSON}")
    out["nl"] = {
        r["node"]: r["description"]
        for r in json.loads(NL_JSON.read_text(encoding="utf-8"))["descriptions"]
        if r.get("status") == "ok" and r.get("description")
    }
    return out


def render_etp(a: str, b: str) -> str:
    return (
        "Two identities for a single binary operation, written \u25c7.\n"
        f"{SCOPE}\n\n"
        f"Law A:  {a}\n"
        f"Law B:  {b}\n\n"
        f"{QUESTION}"
    )


def render_latex(a: str, b: str) -> str:
    return (
        "Two identities for a single binary operation, written "
        "$\\diamond$, given in LaTeX.\n"
        f"{SCOPE}\n\n"
        f"Law A:\n$$ {a} $$\n\n"
        f"Law B:\n$$ {b} $$\n\n"
        f"{QUESTION}"
    )


def render_lean(a: str, b: str) -> str:
    return (
        "Two laws for a magma, written as Lean 4 propositions.\n"
        f"{SCOPE}\n\n"
        "```lean\n"
        "class Magma (\u03b1 : Type u) where\n"
        "  op : \u03b1 \u2192 \u03b1 \u2192 \u03b1\n\n"
        "infixl:65 \" \u25c7 \" => Magma.op\n\n"
        f"def LawA (G : Type u) [Magma G] : Prop := {a}\n\n"
        f"def LawB (G : Type u) [Magma G] : Prop := {b}\n"
        "```\n\n"
        "Is the following a theorem?\n\n"
        "```lean\n"
        "theorem question (G : Type u) [Magma G] : LawA G \u2192 LawB G\n"
        "```"
    )


def render_nl(a: str, b: str) -> str:
    return (
        "Two identities for a single binary operation are described below in "
        "words.\n"
        f"{SCOPE}\n\n"
        f"Law A: {a}\n\n"
        f"Law B: {b}\n\n"
        f"{QUESTION}"
    )


def render_py_lambda(a: str, b: str) -> str:
    return (
        "Two laws for a binary operation, written as Python predicates. Each "
        "takes the operation `op` followed by one argument per variable, and "
        "the law holds for `op` exactly when the predicate returns True for "
        "every assignment of those arguments to elements of the underlying "
        "set.\n"
        f"{SCOPE}\n\n"
        "```python\n"
        f"law_a = {a}\n\n"
        f"law_b = {b}\n"
        "```\n\n"
        f"{QUESTION}"
    )


def render_py_cayley(a: str, b: str) -> str:
    # The catalogue emits every checker under the same name; give the two sides
    # distinct names so the block reads as one coherent program.
    a = re.sub(r"^def law\(", "def law_a(", a.strip())
    b = re.sub(r"^def law\(", "def law_b(", b.strip())
    return (
        "Two laws for a binary operation, written as Python checkers over a "
        "Cayley table. `table[i][j]` is the result of combining element `i` "
        "with element `j`, and a checker returns True exactly when the law it "
        "encodes holds throughout that table.\n"
        "The checkers are finite, but the question below is about the laws "
        "they encode. " + SCOPE + "\n\n"
        "```python\n"
        f"{a}\n\n"
        f"{b}\n"
        "```\n\n"
        f"{QUESTION}"
    )


RENDERERS = {
    "etp": render_etp,
    "latex": render_latex,
    "lean": render_lean,
    "nl": render_nl,
    "py_lambda": render_py_lambda,
    "py_cayley": render_py_cayley,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--infile", type=Path, default=HERE / "implications.json")
    ap.add_argument("--out", type=Path, default=HERE / "implications_rendered.json")
    ap.add_argument(
        "--check",
        action="store_true",
        help="assert no prompt leaks an ETP equation number, then print samples",
    )
    args = ap.parse_args()

    if not args.infile.exists():
        sys.exit(f"missing {args.infile}\nrun `python3 build_implications.py` first")
    payload = json.loads(args.infile.read_text(encoding="utf-8"))
    catalogues = load_catalogues()

    rendered = []
    for rec in payload["implications"]:
        a_node, b_node = rec["hypothesis"], rec["conclusion"]
        reps = {}
        for name in REPRESENTATIONS:
            cat = catalogues[name]
            if a_node not in cat or b_node not in cat:
                sys.exit(f"{rec['id']}: {name} catalogue lacks node {a_node} or {b_node}")
            reps[name] = {
                "hypothesis": cat[a_node],
                "conclusion": cat[b_node],
                "prompt": RENDERERS[name](cat[a_node], cat[b_node]),
            }
        rendered.append({**rec, "representations": reps})

    out = {
        "meta": {
            **payload["meta"],
            "generator": "implications/build_representations.py",
            "rendered_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "representations": list(REPRESENTATIONS),
            "sources": {k: str(v[0].relative_to(REPO)) for k, v in SOURCES.items()}
            | {"nl": str(NL_JSON.relative_to(REPO))},
            "question": QUESTION,
            "scope_clause": SCOPE,
        },
        "implications": rendered,
    }
    args.out.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    n_prompts = len(rendered) * len(REPRESENTATIONS)
    print(f"wrote {args.out}")
    print(f"  {len(rendered)} implications x {len(REPRESENTATIONS)} representations = {n_prompts} prompts")

    if args.check:
        # A bare number matching either side's ETP index would be a retrieval
        # shortcut. Only the catalogue-derived law text can carry per-implication
        # data; the surrounding framing is fixed boilerplate authored above (and
        # legitimately contains numerals -- "Lean 4", "infixl:65").
        leaks = 0
        for rec in rendered:
            for name, rep in rec["representations"].items():
                law_text = f"{rep['hypothesis']}\n{rep['conclusion']}"
                for node in (rec["hypothesis"], rec["conclusion"]):
                    if re.search(rf"\b{node}\b", law_text):
                        print(f"  LEAK {rec['id']}/{name}: node {node} appears in law text")
                        leaks += 1
        print(f"  node-number leak check: {leaks} leak(s)")
        lengths = {
            name: sum(len(r["representations"][name]["prompt"]) for r in rendered) / len(rendered)
            for name in REPRESENTATIONS
        }
        print("  mean prompt chars: " + ", ".join(f"{k}={v:.0f}" for k, v in lengths.items()))
        if leaks:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
