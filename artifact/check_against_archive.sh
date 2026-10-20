#!/usr/bin/env bash
# Check this repository against the paper's data archive without model calls.
#
#   bash artifact/check_against_archive.sh /path/to/semantic-drift-vericodegen
#
# 1. Inputs: if ETP_OUTCOMES points to 2024-11-10-outcomes.json.zip, runs
#    prepare_experiment.py and compares every generated catalogue, the sample,
#    the prompts, the notes and the oracle matrix with the archive's copies
#    (content only; build timestamps and source paths are ignored).
# 2. Grading: regrades the archive's stored responses with this repository's
#    grader, reruns the analysis and the three follow-up reports, and runs the
#    archive's numerical checker. Any failed check is a failing exit status,
#    including previously documented differences from the historical grader.
#    A count of 25 failures is not sufficient to establish which values changed.
#
# Nothing is written to this repository or to the archive; work happens in a
# temporary copy. No model API calls are made. uv may download dependencies.
set -euo pipefail
ARCHIVE="$(cd "${1:?usage: check_against_archive.sh /path/to/semantic-drift-vericodegen}" && pwd)"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
test -f "$ARCHIVE/check_paper_numbers.py" || { echo "not the data archive: $ARCHIVE" >&2; exit 2; }

if command -v uv >/dev/null 2>&1; then
    PY=(uv run --no-project --python 3.12 --with numpy --with scipy --with matplotlib --with pandas
        --with statsmodels --with openai --with httpx --with tiktoken python)
else
    PY=(python3)
fi

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
# Copy only executable research inputs, not credentials or local environments.
for directory in oracle translate semantic-diff-test; do
    rsync -a --exclude '.env' --exclude '.env.*' --exclude __pycache__ \
        --exclude .cache --include '*/' --include '*.py' --exclude '*' \
        "$REPO/$directory/" "$WORK/$directory/"
done
cp "$REPO/prepare_experiment.py" "$WORK/"
export ETP_EQUATIONS="$ARCHIVE/etp/equations.txt"

echo "== 1. experiment inputs"
if [ -n "${ETP_OUTCOMES:-}" ]; then
    (cd "$WORK" && "${PY[@]}" prepare_experiment.py >/dev/null)
    "${PY[@]}" - "$WORK" "$ARCHIVE" <<'PY'
import json, sys
from pathlib import Path
work, archive = Path(sys.argv[1]), Path(sys.argv[2])
IGNORE = {"generated_at", "source", "compiled", "etp_source_crosscheck"}
def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if k not in IGNORE}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o
files = sorted(p.relative_to(work) for p in work.rglob("*") if p.is_file() and (
    p.name.startswith("etp_equations_") or p.name in {
        "sample.json", "prompts.json", "frame.txt", "note.txt", "prompt_template.txt",
        "example_prompt.txt", "matrix.bin", "matrix_meta.json"}))
bad = []
if not files:
    bad.append("no generated inputs found")
for rel in files:
    a, b = work / rel, archive / rel
    if not b.exists():
        bad.append(f"missing in archive: {rel}"); continue
    if a.suffix == ".json":
        same = strip(json.loads(a.read_text())) == strip(json.loads(b.read_text()))
    else:
        same = a.read_bytes() == b.read_bytes()
    if not same:
        bad.append(f"content differs: {rel}")
print("\n".join(bad) if bad else f"PASS {len(files)} generated inputs match the archive")
sys.exit(1 if bad else 0)
PY
else
    echo "SKIP (set ETP_OUTCOMES to the ETP 2024-11-10-outcomes.json.zip to regenerate and compare)"
fi

echo "== 2. grading the stored responses with this repository's code"
cd "$ARCHIVE/semantic-diff-test"
find . \( -name 'raw-*.jsonl' -o -path './ablation/*.jsonl' -o -path './control_probe/*.jsonl' \
          -o -path './dose_confusable/*.jsonl' -o -path './kimi-k2-partial/*.jsonl' \) -print0 |
    while IFS= read -r -d '' f; do mkdir -p "$WORK/semantic-diff-test/$(dirname "$f")"; cp "$f" "$WORK/semantic-diff-test/$f"; done
cd "$ARCHIVE"
for f in semantic-diff-test/sample.json semantic-diff-test/prompts.json semantic-diff-test/frame.txt \
         oracle/data/matrix.bin oracle/data/matrix_meta.json; do
    mkdir -p "$WORK/$(dirname "$f")"; cp "$f" "$WORK/$f"
done
while IFS= read -r -d '' f; do
    mkdir -p "$WORK/$(dirname "$f")"; cp "$f" "$WORK/$f"
done < <(find translate -name 'etp_equations_*.json' -print0)
# Follow-up reports read the archived notation notes even when regeneration
# was skipped. Never substitute locally edited notes for the archived inputs.
while IFS= read -r -d '' f; do
    mkdir -p "$WORK/$(dirname "$f")"; cp "$f" "$WORK/$f"
done < <(find semantic-diff-test -name note.txt -print0)
cp semantic-diff-test/analyze.py "$WORK/semantic-diff-test/"      # the paper's analysis script
cp check_paper_numbers.py "$WORK/"
cd "$WORK/semantic-diff-test"
"${PY[@]}" grade.py
"${PY[@]}" analyze.py
for s in ablate_notes probe_control dose_confusable; do "${PY[@]}" "$s.py" --report >/dev/null; done
cd "$WORK"
if "${PY[@]}" check_paper_numbers.py; then
    echo "PASS numerical checks completed successfully"
else
    status=$?
    echo "FAIL numerical checks exited with status $status." >&2
    echo "Historical grader differences are documented in ARTIFACT.md;" >&2
    echo "they are not automatically accepted as a successful reproduction." >&2
    exit "$status"
fi
