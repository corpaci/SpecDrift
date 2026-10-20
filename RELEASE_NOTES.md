# Release preparation

These are notes for the next code release; no version or release date is assigned.

## Changes

- Added a brief project README and guides for preparation, offline replay,
  new response collection, follow-ups, converters, and earlier studies.
- Linked the code/data archive cited in the final submission.
- Updated the manuscript PDF to the clean final export, preserving its checklist.
- Made the archive comparison return failure when numerical checks fail.
- Aligned follow-up report labels with certified recovery and the
  fewer-variable proxy; retained historical JSON field names and calculations.
- Ignored credentials, generated outputs, caches, and LaTeX build files.
- Clarified third-party and manuscript attribution.
- Updated the MIT copyright attribution to Malhar Alpesh Patel and Luiza
  Cristina Corpaci, as confirmed by the author.

## GitHub metadata

Description:

> Code for When Specifications Drift: measuring semantic preservation across LLM representations of algebraic equations.

Topics: `semantic-drift`, `llm-evaluation`, `formal-methods`,
`autoformalization`, `reproducible-research`.

## Outstanding release information

- The cited Zenodo record needs a working public download. The record API
  returned HTTP 404 during this review; historical replay remains unverified.
- The draft in `docs/PAPER_CODE_DIFFERENCES_DRAFT.md` needs author review
  and verification against the archive.
- Matching final LaTeX source is needed for a reproducible manuscript build.
- A separate paper/template license has not been established here.
  Their inclusion does not assign a new license to them.

The oracle-validation, checkpoint, dependency-pinning, and CI changes discussed
in the review are deferred. This release preparation does not implement them.
