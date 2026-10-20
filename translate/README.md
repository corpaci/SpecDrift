# Deterministic encodings

Each encoding has a converter/reader and a `build_catalogue.py` entry point.
The main experiment uses all 17 plus canonical ETP infix as its control.
These encodings are generated mechanically, including the prose encodings.

| Directory | Representation | Converter |
|---|---|---|
| `latex` | Explicitly parenthesized LaTeX infix | `latexify.py` |
| `lean` | Universally quantified Lean proposition | `leanify.py` |
| `tptp` | First-order equality in TPTP | `tptpify.py` |
| `smtlib` | Universally quantified SMT-LIB equality | `smtify.py` |
| `py_lambda` | Python predicate using `op(a, b)` | `lambdify.py` |
| `py_cayley_table` | Python checker over a finite operation table | `cayleyify.py` |
| `text` | Infix words with explicit bracket words | `textify.py` |
| `text2` | Nested “the diamond of A and B” phrases | `prefixify.py` |
| `word_problem` | Fixed welding scenario | `storify.py` |
| `polish` | Polish (prefix) notation | `polishify.py` |
| `rpn` | Reverse Polish (postfix) notation | `rpnify.py` |
| `ssa` | Ordered intermediate assignments | `ssaify.py` |
| `slots` | Nested lists with integer variable identifiers | `slotify.py` |
| `ascii_tree` | Indented ordered tree, supplied as text | `treeify.py` |
| `graphviz` | Graphviz DOT source, supplied as text | `dotify.py` |
| `json_ast` | JSON term tree | `jsonify.py` |
| `confusable_vars` | Infix with distinct look-alike variable names | `confusify.py` |

From the repository root:

```sh
python3 translate/rpn/rpnify.py --selftest
python3 translate/rpn/rpnify.py --help
ETP_EQUATIONS=/absolute/path/to/equations.txt python3 translate/rpn/build_catalogue.py
```

Builders write generated catalogue files alongside the converter and run
inverse checks over the catalogue. `prepare_experiment.py` builds all 17
with the defaults used by the study. Use each builder's `--help` for options;
changing them creates a different experiment.

Inverse checks compare term structure, allowing bijective renaming for the
confusable encoding. The Python predicates also have finite-table checks.
A check on a finite Cayley table does not decide implication over all magmas.

`_catalogue.py` contains shared builder/CLI helpers. `nl/openrouter.py` is
API transport, not an eighteenth deterministic encoding.
