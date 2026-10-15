#!/usr/bin/env bash
# Check this repository against the paper's data archive, offline.
#
#   bash artifact/check_against_archive.sh /path/to/semantic-drift-vericodegen
#
# 1. Inputs: if ETP_OUTCOMES points to 2024-11-10-outcomes.json.zip, runs
#    prepare_experiment.py and compares every generated catalogue, the sample,
#    the prompts, the notes and the oracle matrix with the archive's copies
#    (content only; build timestamps and source paths are ignored).
# 2. Grading: regrades the archive's stored responses with this repository's
#    grader, reruns the analysis and the three follow-up reports, and runs the
#    archive's check of the 427 numbers printed in the paper. The expected result
#    is 402 of 427: the 25 values listed in ARTIFACT.md move because this grader
#    is newer than the one that produced the paper.
#
# Nothing is written to this repository or to the archive; work happens in a
# temporary copy. No model API calls are made.
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
rsync -a --exclude .git --exclude submission --exclude template --exclude '*.zip' "$REPO/" "$WORK/"
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
         oracle/data/matrix.bin oracle/data/matrix_meta.json $(find translate -name 'etp_equations_*.json'); do
    mkdir -p "$WORK/$(dirname "$f")"; cp "$f" "$WORK/$f"
done
cp semantic-diff-test/analyze.py "$WORK/semantic-diff-test/"      # the paper's analysis script
cp check_paper_numbers.py "$WORK/"
cd "$WORK/semantic-diff-test"
"${PY[@]}" grade.py | head -1
"${PY[@]}" analyze.py | tail -1
for s in ablate_notes probe_control dose_confusable; do "${PY[@]}" "$s.py" --report >/dev/null; done
cd "$WORK"
"${PY[@]}" check_paper_numbers.py || true
