# Third-party notices

## Equational Theories Project data

The experiment uses the ETP catalogue (`data/equations.txt`) and the published
implication outcomes (`data/2024-11-10-outcomes.json.zip`) from the
[Equational Theories Project](https://github.com/teorth/equational_theories).
This repository does not contain them: `prepare_experiment.py` reads them from
the paths in `ETP_EQUATIONS` and `ETP_OUTCOMES`. The paper's data archive
(see `ARTIFACT.md`) ships the catalogue together with the matrix built from
the outcomes.

The upstream [licence](https://github.com/teorth/equational_theories/blob/main/LICENSE)
is the Apache License 2.0, with the notice:

> Copyright 2025 Contributors of the Equational Theories Project

A copy is included in `ETP-APACHE-2.0.txt`. These data are not relicensed by
this repository's MIT licence (`LICENSE`). The upstream revision used was
`7e276a2d05e84e3eef02432abfd0718e78f7abfa`.

`oracle/build_matrix.py` turns the published outcomes into a byte matrix and
metadata, merging explicit and implicit results of the same status. From that
revision, the catalogue and the built matrix have these SHA-256 values:

| File | SHA-256 |
|---|---|
| `data/equations.txt` (upstream) | `e30e1a6735011ff36fdb228d37b232eb7cda9d4a836cbbefc69c07e6871c8010` |
| `oracle/data/matrix.bin` (built by `prepare_experiment.py`) | `13b1a18a53ded52a517d59b841060e616302ccf04c6425ba39444e468510b70e` |

The Lean proofs and counterexamples behind those outcomes are not included.

## Model responses

This repository contains no model responses. The responses analysed in the
paper are in its data archive, which carries its own notice. They were
generated through the OpenRouter API by these endpoints:

| Endpoint (OpenRouter ID) | Developer |
|---|---|
| `mistralai/mistral-small-3.2-24b-instruct` | Mistral AI |
| `qwen/qwen3-30b-a3b-instruct-2507` | Alibaba Qwen |
| `microsoft/phi-4` | Microsoft |
| `google/gemini-2.5-flash` | Google |
| `meta-llama/llama-4-maverick` | Meta |
| `x-ai/grok-4.20` | xAI |
| `deepseek/deepseek-v3.2` | DeepSeek |
| `openai/gpt-5.2` | OpenAI |
| `anthropic/claude-opus-5` | Anthropic |
| `moonshotai/kimi-k2` (533 partial rows, excluded from all results) | Moonshot AI |

Responses you collect with `run_experiment.py` are subject to OpenRouter's
terms and to the terms of each model's developer.
