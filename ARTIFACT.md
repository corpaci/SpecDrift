# Artifact: When Specifications Drift

Code for *When Specifications Drift: Measuring Semantic Preservation Across
LLM Representations* (Malhar Patel and Luiza Cristina Corpaci, NeurIPS 2026
Workshop on AI for Verifiable Coding).

The artifact has two parts:

- **This repository**: the oracle, the 17 converters with their inverse
  readers, the sampling and prompt code, the experiment runners and the grader.
- **The data archive** `semantic-drift-vericodegen.zip`, the paper's
  supplementary material: the 153,000 stored responses, the generated inputs,
  the graded results, the analysis script, and `check_paper_numbers.py`, which
  checks 427 numbers printed in the paper. Its README describes it.

Nothing below calls a model API unless stated.

## 1. Regenerate the experiment inputs

Requires Python 3.10+ with `numpy` and `tiktoken`, plus the ETP catalogue and
outcomes at upstream revision `7e276a2` (see `THIRD_PARTY_NOTICES.md`).

```sh
export ETP_EQUATIONS=/path/to/equational_theories/data/equations.txt
export ETP_OUTCOMES=/path/to/equational_theories/data/2024-11-10-outcomes.json.zip
python3 prepare_experiment.py
```

This writes the 17 catalogues of 4,694 laws, the oracle matrix
(`oracle/data/matrix.bin`, SHA-256 `13b1a18a…`), the 500-law sample, the prompt
frame, the 18 notation notes and the 9,000 prompts. Each converter reads its
whole catalogue back and prints `verified: True`. Their content is identical to
the inputs used in the paper; only build timestamps and source paths differ.
Step 3 checks this.

## 2. Reproduce the paper's numbers

Unzip the data archive and run, inside it:

```sh
bash regenerate.sh
```

It regrades the stored responses, reruns the analysis and the three follow-up
reports, and ends with `427 of 427 checks passed.` The archive uses the code
at the commit that produced the paper (`6c947fc` of the research repository).
That is the code to use to reproduce the paper exactly.

## 3. Check this repository against the archive

```sh
export ETP_OUTCOMES=/path/to/2024-11-10-outcomes.json.zip   # optional: enables the input check
bash artifact/check_against_archive.sh /path/to/semantic-drift-vericodegen
```

The script works in a temporary copy and changes neither this repository nor
the archive. Expected output:

- `PASS 76 generated inputs match the archive`. This is skipped if `ETP_OUTCOMES` is unset.
- `402 of 427 checks passed.` The 25 other values move because this
  repository's grader is newer than the paper's (see below).

## How this grader differs from the paper's

This repository's oracle adds an `equal` verdict (the two laws are the same
catalogue entry). `grade.py` counts it as recovery, exactly as `equivalent`,
and records it separately in `oracle_label`. Its extraction also reads a few
Lean and TPTP answers that the paper's grader rejected. On the 81,000 main
responses, 12 outcomes change:

| Representation | Model | Change | Responses |
|---|---|---|---|
| Lean | DeepSeek V3.2 | unparseable to equivalent | 4 |
| Lean | Llama 4 Maverick | unparseable to off-catalogue | 2 |
| Lean | Llama 4 Maverick | equivalent to off-catalogue | 1 |
| TPTP | Phi-4 | off-catalogue to equivalent | 3 |
| TPTP | Phi-4 | unparseable to equivalent | 2 |

Ten more change in the repeat draws. As a result, these printed values differ
when the stored responses are graded with this repository:

| Paper | Value in the paper | With this repository |
|---|---|---|
| Main equivalent / unparseable (Section 5.2) | 42,151 / 2,925 | 42,159 / 2,917 |
| Equivalent via a different catalogue entry | 2,281 | 2,282 |
| Table 7, TPTP row (E, O, P) | 3,155, 485, 113 | 3,160, 482, 111 |
| Table 7, Lean row (E, O, P) | 2,613, 1,045, 121 | 2,616, 1,048, 115 |
| Table 5, TPTP (all answered, common, post-stratified) | 70.1, 70.0, 68.8 | 70.2, 70.1, 68.9 |
| Table 5, Lean common subset | 58.5 | 58.6 |
| Table 6, TPTP (equivalent, interval) | 3,155, 68.8–71.4 | 3,160, 68.9–71.5 |
| Table 6, Lean (equivalent, interval) | 2,613, 56.6–59.5 | 2,616, 56.7–59.6 |
| Repeat triples with one outcome (Section 5.6) | 18,704 | 18,706 |
| Table 4, Phi-4 recovery / DeepSeek strict | 43.7 / 46.9 | 43.8 / 47.0 |
| Appendix C regression, order coefficient (p) | −0.0169 (0.566) | −0.0172 (0.559) |
| Appendix C regression, five other coefficients | as printed | differ in the fourth decimal |

No conclusion changes. The span across representations, the Cochran and
McNemar results, the look-alike-name figures and all follow-up results are
identical.

## 4. Collect new responses (costs money)

```sh
export OPENROUTER_API_KEY=...
cd semantic-diff-test
python3 run_experiment.py --smoke 2        # a small paid check
python3 run_experiment.py --phase main     # 81,000 calls
python3 run_experiment.py --phase repeat   # 48,600 calls
python3 grade.py
```

The follow-up experiments use `ablate_notes.py`, `probe_control.py` and
`dose_confusable.py`. Run each with `--run` to collect and `--report` to
summarise. The full study cost about $104 in API charges. Hosted models change
and not every provider honours a seed, so new responses will not match the
stored ones exactly.

## Requirements

Python 3.10 or later. Grading uses the standard library only. The runners and
reports need `openai`, `httpx`, `numpy`, `scipy`, `matplotlib` and `tiktoken`.
The archive's analysis also needs `pandas` and `statsmodels`.

## Licences

The code is MIT-licensed (`LICENSE`). For the ETP data and the model
endpoints, see `THIRD_PARTY_NOTICES.md`.
