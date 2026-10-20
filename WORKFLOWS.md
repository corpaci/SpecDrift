# Research workflows

Commands below start in the repository root unless a `cd` is shown.
Python 3.10 or later is required. Parser tests and grading use the standard
library; input preparation needs `numpy` and `tiktoken`. Runners and follow-up
reports also use `openai`, `httpx`, `scipy`, and `matplotlib`. The archive's
analysis uses `pandas` and `statsmodels`. Dependency pinning is not yet provided.

## Choose a workflow

| Goal | Entry point | Required inputs | Model API calls |
|---|---|---|---|
| Parse an equation | `oracle/normalizer.py` | Equation text | None |
| Compare meanings | `oracle/oracle.py` | ETP catalogue and built matrix | None |
| Rebuild experiment inputs | `prepare_experiment.py` | Historical ETP catalogue and outcomes | None |
| Reproduce reported numbers | Archive's `regenerate.sh` | Complete historical archive | None |
| Compare current code with historical responses | `artifact/check_against_archive.sh` | Complete historical archive | None |
| Collect main/repeat responses | `semantic-diff-test/run_experiment.py` | Prepared inputs and API key | Paid |
| Run follow-up studies | Three scripts listed below | Prepared inputs; API key for collection | Paid only with `--run` |

## 1. Inspect the parser and converters

These examples need no ETP data or API key:

```sh
python3 oracle/normalizer.py --json "x = x * y"
python3 -m unittest discover -s oracle -v
python3 translate/rpn/rpnify.py --selftest
python3 translate/py_lambda/lambdify.py --selftest
```

Every deterministic converter supports `--selftest` and `--help`.
See [the converter guide](translate/README.md) for all 17 encodings.
Converter round trips check the implemented encoder/reader pair; they are
not independent proofs of every external language's semantics.

## 2. Prepare the main study

Obtain `data/equations.txt` and `data/2024-11-10-outcomes.json.zip` from
ETP revision `7e276a2d05e84e3eef02432abfd0718e78f7abfa`.
[Third-party notices](THIRD_PARTY_NOTICES.md) record provenance and hashes.
Use the historical snapshot when comparing with the paper.

```sh
export ETP_EQUATIONS=/absolute/path/to/equations.txt
export ETP_OUTCOMES=/absolute/path/to/2024-11-10-outcomes.json.zip
python3 prepare_experiment.py
```

Alternatively set `ETP_ROOT` to a checkout containing both files.
Preparation writes the 17 catalogues, matrix, 500-law sample, 150-law
repeat subset, shared frame, 18 notes, and 9,000 model-independent prompts.
It overwrites generated input files. The first tokenizer use can download
`cl100k_base` data; preparation does not call a model API.

`python3 prepare_experiment.py --config-only` writes the embedded frame,
notes, and historical prose prompts without building data-dependent inputs.

After preparation:

```sh
python3 oracle/oracle.py --selftest
python3 oracle/oracle.py --intended "x = x * y" --generated "x = x * x" --json
```

The second example is weaker from the generated equation's perspective.
`equal` and `equivalent` both indicate semantic preservation.
`unknown`, `outside-fragment`, and parse/mapping failures do not establish
semantic disagreement. See [oracle documentation](oracle/README.md).

## 3. Replay saved responses

Download and extract the [archive cited by the paper](https://doi.org/10.5281/zenodo.23392977).
Use its historical code to reproduce the reported numbers:

```sh
cd /absolute/path/to/semantic-drift-vericodegen
bash regenerate.sh
```

The existing artifact guide records an expectation of 427 passing numerical
checks. That expectation requires the complete archive and has not been
revalidated against the final submission in this checkout.

To evaluate the current repository against the saved responses, return to
the repository root:

```sh
bash artifact/check_against_archive.sh /absolute/path/to/semantic-drift-vericodegen
```

This works in a temporary directory and leaves the archive unchanged.
Setting `ETP_OUTCOMES` also enables generated-input comparison; otherwise
that stage is explicitly skipped. If `uv` is installed, the script may
download Python/dependencies. No model calls are made.

The current grader differs from the historical grader. Numerical mismatches
produce a nonzero exit, including previously documented differences.
Read the checker output rather than treating a failed comparison as a
successful reproduction. See [ARTIFACT.md](ARTIFACT.md).

## 4. Collect and grade new responses

These collection commands spend API credits. Keep the historical archive
separate; use a fresh working copy for a new experiment.

```sh
export OPENROUTER_API_KEY=your_key
cd semantic-diff-test
python3 run_experiment.py --smoke 2 --models gpt-5.2
python3 grade.py --tag smoke-
python3 run_experiment.py --status
```

The selected-model smoke command schedules 36 calls: two laws in each of
18 representations. Omitting `--models` schedules 324 calls across nine models.
Smoke output uses `smoke-<model>.jsonl`; full runs use `raw-<model>.jsonl`,
inside each representation directory.

```sh
python3 run_experiment.py --phase main
python3 run_experiment.py --phase repeat
python3 grade.py
```

The main phase schedules 81,000 calls; repeats schedule 48,600 more.
Running without `--phase` selects both. `--models` accepts the slugs listed
in `run_experiment.py`. Hosted endpoints and supported settings can change;
these are the historical study settings, not a guarantee of current availability.

The grader writes `results/graded.json` (or `graded-smoke.json` for smoke
data). It retains the first non-error response per model/representation/law/draw
key, allowing an error to be replaced by a later response. Recovery excludes
transport/filter losses from its denominator but includes parse and coverage
failures as unsuccessful certification. Failure to certify is not proof of error.
`strict` means the cleaned whole response was accepted, not raw-format compliance.

The standalone main analysis script, `analyze.py`, is not in this checkout.
Use the archive's analysis and instructions to produce main tables and figures.

### Resumption limitation

Main checkpoints check selected settings and the shared-frame hash, but not
every note, rendered input, or sampled node. Follow-up checkpoints lack that
configuration header. Resume only with unchanged inputs and code. Start a
fresh working copy when changing the experiment; do not mix runs in place.

## 5. Follow-up studies

After preparation, run these from `semantic-diff-test/`.

| Script | Design | Fresh calls | Output directory |
|---|---|---:|---|
| `ablate_notes.py` | Four models × four encodings × four note conditions × 150 laws | 9,600 | `ablation/` |
| `probe_control.py` | Seven models × canonical/LaTeX × four framing conditions × 150 laws | 8,400 | `control_probe/` |
| `dose_confusable.py` | Six models × six naming schemes × 150 laws | 5,400 | `dose_confusable/` |

Each script supports the same workflow:

```sh
python3 ablate_notes.py --dry-run
python3 ablate_notes.py --run
python3 ablate_notes.py --report
```

Substitute `probe_control.py` or `dose_confusable.py` as needed.
`--dry-run` previews inputs, `--run` collects paid responses, and `--report`
regrades saved rows and writes summaries and figures without model calls.
Reports require existing response files and the built oracle.
Summary filenames are `ablation_summary.json`, `control_probe_summary.json`, and
`dose_summary.json`; figures go to `figures/`.

The note conditions are none, current, padded, and generous. The framing
conditions vary an explicit preservation instruction and the magma preamble.
Naming schemes are categorical; fewer distinct variables is a proxy, not
proof that an answer arose solely by merging variables.
Historical JSON keys such as `accuracy` and `merge` are retained for
compatibility with existing analysis; their meanings follow these definitions.

## 6. Earlier exploratory work

`implications/` studies model judgments of implications, rather than recovery
of one encoded equation. It is separate from the paper's 153,000-call study.
See [its guide](implications/README.md) for required data and execution order.

`translate/nl/openrouter.py` is shared API transport. The generated-prose
catalogue and the original prose generation/reconstruction runners are not
included here. The historical prompts written by `--config-only` do not
constitute a complete runnable prose study.
