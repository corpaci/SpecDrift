"""Prepare inputs for the anonymous code-only supplement (Python 3.10+).

Install dependencies:
    python3 -m pip install openai httpx numpy scipy matplotlib pandas statsmodels tiktoken

Provide upstream ETP equations and the historical certified outcomes snapshot:
    export ETP_EQUATIONS=/path/to/equations.txt
    export ETP_OUTCOMES=/path/to/2024-11-10-outcomes.json.zip
Alternatively set ETP_ROOT to your equational_theories checkout.

Prepare catalogues, the oracle matrix, sample, and recovery prompts:
    python3 prepare_experiment.py

Then launch a small paid API smoke run or the full study:
    export OPENROUTER_API_KEY=your_key
    cd semantic-diff-test
    python3 run_experiment.py --smoke 2
    python3 run_experiment.py --phase main
    python3 run_experiment.py --phase repeat
    python3 grade.py

Follow-up runners: ablate_notes.py, probe_control.py, dose_confusable.py.
Use --run to collect responses and --report to grade their results.
Earlier prose and implication-study source is also retained; those workflows
need their separately generated input datasets and upstream ATP results.

No credentials, original outputs, notebooks, analysis scripts, Markdown,
repository history, compiled artifacts, or local environments are included.
Follow-up statistics and plotting helpers are included in report_support.py.
The paper groups both current oracle verdicts equal/equivalent as recovery;
grade.py keeps this reporting rule and records oracle_label separately.
The first token-count check needs cl100k_base tokenizer data, downloaded by
tiktoken unless already available through TIKTOKEN_CACHE_DIR.
Configuration is embedded here; generated inputs appear only after preparation.
Preparation does not call model APIs. Full response collection incurs charges.
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FRAME = 'A single identity that holds in a magma is written below. Recover the identity\nitself.\n\nThe identity involves one binary operation and holds for all values of its\nvariables. The operation is on an arbitrary set: it is not assumed to be\nassociative or commutative, and there is no identity element.\n\n{note}\n\nRequirements:\n- Output only the identity, on one line, in the form: left side = right side.\n- Write the operation as ◇ and make every grouping explicit with parentheses:\n  write x ◇ (y ◇ z) or (x ◇ y) ◇ z, never x ◇ y ◇ z.\n- Use single lowercase letters for variables; you may choose any letters.\n- Do not restate the input, do not name the identity, do not explain, and do not\n  add any other text.\n\n{body}\n'
NOTES = {'ascii_tree': "Each ◇ is one operation. Variables are the lowercase letters at the leaves. Grouping is shown by indentation: a node's two children are its arguments, the left one first.", 'confusable_vars': 'The operation is written ◇ between its two arguments. Variables are the identifiers; different identifiers are different variables. Grouping is shown by parentheses.', 'etp_canonical': 'The operation is written ◇ between its two arguments. Variables are single lowercase letters. Grouping is shown by parentheses around each nested operation.', 'graphviz': "This is Graphviz DOT. Each ◇ node is an operation. Variables are letters in node labels. A node's two out-edges are its arguments, left first.", 'json_ast': 'This is JSON. The operation is an object keyed ◇ holding two arguments. Variables are the strings. Grouping is shown by how the objects nest.', 'latex': 'This is LaTeX. The operation is written \\diamond between its two arguments. Variables are single letters. Grouping is shown by parentheses.', 'lean': 'This is Lean. The operation is written ◇ between its two arguments. Variables are the ones bound by the ∀. Grouping is shown by parentheses.', 'polish': 'The operation is ◇, written before its two arguments. Variables are single lowercase letters. Grouping is shown by position: each ◇ takes the two terms after it.', 'py_cayley_table': 'This is Python. The operation is the lookup table[a][b]. Variables are the names quantified in the comprehension. Grouping is shown by how the lookups nest.', 'py_lambda': "This is Python. The operation is the call op(a, b). Variables are the lambda's parameters after op. Grouping is shown by how the calls nest.", 'rpn': 'The operation is ◇, written after its two arguments. Variables are single lowercase letters. Grouping is shown by position: each ◇ takes the two values before it.', 'slots': 'The operation is a two-element list. Variables are numbers, and equal numbers are the same variable. Grouping is shown by how the lists nest; the outermost list holds the two sides.', 'smtlib': 'This is SMT-LIB. The operation is the application (op a b). Variables are the names bound by the forall. Grouping is shown by how the applications nest.', 'ssa': 'The operation is written ◇ between its two arguments. Variables are single lowercase letters; names starting with t are intermediate results. Grouping is shown by which results each line uses.', 'text': 'The operation is the word diamond between its two arguments. Variables are single lowercase letters. Grouping is shown by the words open bracket and close bracket.', 'text2': "The operation is the phrase 'the diamond of A and B'. Variables are single lowercase letters. Grouping is shown by how those phrases nest.", 'tptp': 'This is TPTP. The operation is the term op(A, B). Variables are the upper-case names bound by the quantifier. Grouping is shown by how the terms nest.', 'word_problem': 'The operation is welding one part to another, in that order. Variables are the lowercase letters naming parts. Grouping is shown by which part each welding uses.'}


# Historical defaults used by the earlier generated-English study.
EARLIER_PROMPTS = {'translate/nl/prompts/structural.txt': 'Describe the following identity in plain English, for a mathematician who cannot see the formula and must be able to write it down again from your words alone.\n\nThe identity holds for a single binary operation, written ◇, over all values of its variables.\n\nRequirements:\n- State the structure exactly: which variables appear, how many times each one occurs, on which side, and how the operation is grouped and nested.\n- Use words only. Do not use ◇, asterisks, dots, LaTeX, parentheses as notation, or any other symbols. You may refer to the variables by their letters.\n- Do not name the law and do not say whether it is well known. Never use words like commutative, associative, idempotent, or the name of any named algebraic identity.\n- Do not give consequences, examples, intuition, or commentary. Describe only the identity itself.\n- Output only the description, as a single paragraph.\n\nIdentity: {equation}\n', 'translate/nl/prompts/named.txt': 'Describe the following identity in plain English, for a mathematician who cannot see the formula.\n\nThe identity holds for a single binary operation, written ◇, over all values of its variables.\n\nRequirements:\n- Use words only: no ◇, no LaTeX, no notation. You may refer to the variables by their letters.\n- You may name the law if it has a standard name.\n- Output only the description, as a single paragraph.\n\nIdentity: {equation}\n', 'translate/nl_test/prompts/reconstruct.txt': 'A mathematician has written down, in words alone, one identity that holds in a\nmagma. Recover the identity itself.\n\nThe identity involves a single binary operation, written ◇, and holds for all\nvalues of its variables. Variables are single lowercase letters.\n\nRequirements:\n- Output only the identity, on one line, in the form: left side = right side.\n- Write the operation as ◇ and make every grouping explicit with parentheses:\n  write x ◇ (y ◇ z) or (x ◇ y) ◇ z, never x ◇ y ◇ z.\n- Use exactly the variables the description names, each occurring exactly as\n  often, on the side and in the position it describes.\n- Do not restate the description, do not name the law, do not explain, and do\n  not add any other text.\n\nDescription: {description}\n'}

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config-only", action="store_true", help="write the embedded frames, notes, and earlier prose prompts without building upstream-dependent inputs")
    args = parser.parse_args()
    directory = ROOT / "semantic-diff-test"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "frame.txt").write_text(FRAME, encoding="utf-8")
    for name, note in NOTES.items():
        destination = directory / name
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "note.txt").write_text(note + "\n", encoding="utf-8")
    for relative_path, prompt in EARLIER_PROMPTS.items():
        destination = ROOT / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(prompt, encoding="utf-8")
    if args.config_only:
        return
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for script in sorted((ROOT / "translate").glob("*/build_catalogue.py")):
        subprocess.run([sys.executable, str(script)], cwd=script.parent, env=env, check=True)
    for script in [ROOT / "oracle" / "build_matrix.py", directory / "build_sample.py", directory / "render_prompts.py"]:
        subprocess.run([sys.executable, str(script)], cwd=script.parent, env=env, check=True)


if __name__ == "__main__":
    main()
