# Draft for author review: paper and current code

This text is proposed documentation, not an independently verified replay
of the final submission. It has not replaced the existing difference table
in `ARTIFACT.md`.

## Proposed text

The final submission reports results from the historical experiment and
grader. Use the archived implementation and saved responses cited in the
paper to reproduce those results. Running hosted models again produces a
new experiment; deterministic settings do not guarantee identical responses.

The current repository differs from the historical grader in three ways:

1. The oracle distinguishes `equal` (the same catalogue node) from
   `equivalent` (different nodes with both implications certified).
   The experiment grader combines both into the paper's `equivalent`
   reporting category and retains the distinction in `oracle_label`.
2. Extraction accepts some Lean and TPTP outputs previously rejected.
   The existing artifact guide reports 12 changed main outcomes and ten
   changed repeat outcomes. Those are prior comparison results, not a
   fresh validation against the final submission.
3. The current parser accepts Unicode identifiers and preserves their exact
   code-point identity. The paper's historical parser was ASCII-oriented.
   Echoed Unicode can therefore affect coverage when old responses are
   regraded. This change does not retroactively validate the historical
   homoglyph condition through the newer parser.

The existing guide records 42,151 equivalent and 2,925 unparseable main
responses for the paper, versus 42,159 and 2,917 in its earlier comparison
with newer code. It also records 402/427 passing numerical checks.
These numbers must be rechecked with the exact archived checker and final
paper before being described as the complete current difference set.
In particular, a matching count of failed checks would not show that the
same values changed.

The final submission reports recovery and coverage separately.
An unparseable or out-of-catalogue answer is not a certified semantic error.
Fewer distinct variables is a proxy for variable identification, not proof
of a pure variable-merge edit. The six naming schemes are categories,
not a calibrated numerical scale.

## Review before adopting

- Confirm the archive's accessible record/download and exact historical
  code/checker version. The paper cites `10.5281/zenodo.23392977`;
  the Zenodo record API returned HTTP 404 during this review.
- Verify the existing guide's counts and its claim that follow-up results
  are unchanged under the current Unicode-aware parser.
- Replace old table references using the final paper: model summary is
  Table 3, pooled recovery Table 4, intervals Table 5, exact outcomes
  Table 6, and naming results Table 8. Confirm each numerical row before
  publishing the revised comparison table.
