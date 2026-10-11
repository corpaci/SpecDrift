#!/usr/bin/env bash
# Launch the three-model sweep, one process per model, in parallel.
#
# Safe to run as many times as you like: every process passes --resume, so a
# re-run picks up exactly the cells that are missing from results/<slug>.jsonl
# and re-sends nothing that already landed. That is the recovery path after a
# kill, a dropped connection, or the WSL host going away mid-run.
#
#   ./run_all.sh            # start, or resume, the full sweep
#   ./run_all.sh --status   # show what is done and what is left; makes no calls
set -euo pipefail

cd "$(dirname "$0")"
PYTHON="${PYTHON:-../../.venv/bin/python}"

MODELS=(
  "mistralai/mistral-small-3.2-24b-instruct"
  "google/gemini-2.5-flash"
  "anthropic/claude-opus-4.5"
)

if [[ "${1:-}" == "--status" ]]; then
  exec "$PYTHON" run_judgements.py --all --status
fi

mkdir -p results logs
pids=()
for model in "${MODELS[@]}"; do
  slug="${model##*/}"
  echo "launching $model"
  "$PYTHON" -u run_judgements.py --model "$model" --resume > "logs/$slug.txt" 2>&1 &
  pids+=($!)
done

# Wait for all three; report which (if any) exited non-zero rather than letting
# `set -e` kill the script on the first failure and orphan the others.
failed=0
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    echo "FAILED: ${MODELS[$i]} (see logs/${MODELS[$i]##*/}.txt)" >&2
    failed=1
  fi
done

"$PYTHON" run_judgements.py --all --status
[[ $failed -eq 0 ]] || { echo; echo "re-run ./run_all.sh to resume the failed model(s)"; exit 1; }
