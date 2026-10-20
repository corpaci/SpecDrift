# Earlier implication-judgment experiment

This exploratory workflow asks whether one law implies another. It is not
part of the main recovery experiment or its 153,000-call total.

It needs the built oracle matrix, generated deterministic catalogues,
ETP's `data/2025-08-11-vampire.json.gz`, and the historical generated-prose
file `translate/nl/descriptions-qwen3.json`. That prose file and its generation
runner are not supplied in this checkout. Main-study preparation alone is
therefore insufficient to run this workflow.

After supplying those inputs, from the repository root:

```sh
python3 implications/build_difficulty.py /absolute/path/to/2025-08-11-vampire.json.gz
python3 implications/build_implications.py
python3 implications/build_representations.py --check
```

The first command writes solver-time/method/verdict arrays in
`implications/data/`. The second samples pairs into `implications.json`.
The third writes `implications_rendered.json` with six representations:
canonical infix, LaTeX, Lean, generated prose, Python lambda, and Cayley checker.
`--check` checks the rendered prompts; it still writes the output dataset.

Read the runner's options before collection:

```sh
python3 implications/test_implications/run_judgements.py --help
```

`run_all.sh` collects paid model responses and resumes existing checkpoints.
It defaults to `../../.venv/bin/python` relative to its own directory;
override `PYTHON` with an absolute interpreter path if needed.
Results and logs are written inside `implications/test_implications/`.
`run_all.sh --status` reports progress without model calls.
