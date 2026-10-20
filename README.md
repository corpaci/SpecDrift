# SpecDrift

Code for *When Specifications Drift: Measuring Semantic Preservation Across
LLM Representations*, by Malhar Alpesh Patel and Luiza Cristina Corpaci.

The study presents 500 algebraic equations in 18 representations to nine
language models. Models reconstruct each equation; an implication table from
the Equational Theories Project compares its meaning with the original.
Results distinguish equivalence, weakening, strengthening, incomparability,
and outputs the checker cannot certify.

- [Final submission](submission/paper.pdf)
- [Code and data archive](https://doi.org/10.5281/zenodo.23392977)
- [Workflows and commands](WORKFLOWS.md)
- [Reproduction guide](ARTIFACT.md)
- [Oracle usage](oracle/README.md)

`oracle/` contains the semantic checker, `translate/` the deterministic
encoders and readers, and `semantic-diff-test/` the experiment runners and
grader. `implications/` contains earlier exploratory work.

Run the parser tests without external data or API access:

```sh
python3 -m unittest discover -s oracle -v
```

Code is MIT-licensed. See [third-party notices](THIRD_PARTY_NOTICES.md) for
ETP data and other material.
