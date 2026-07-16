"""Run every `.kfc` script in tests/integration/scripts/ through the real
command path (texttests.script_runner) and compare stdout against its
sibling `.expected` file.

Each `.kfc` uses the same `Board:`/`Commands:` DSL described in the
README (click/jump/wait/print board); each `.expected` holds the exact
text those commands should print.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest

from texttests.script_runner import run_script

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")

SCRIPT_NAMES = sorted(
    name for name in os.listdir(SCRIPTS_DIR) if name.endswith(".kfc")
)


@pytest.mark.parametrize("script_name", SCRIPT_NAMES)
def test_script_output_matches_expected(script_name):
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    expected_path = script_path[: -len(".kfc")] + ".expected"

    with open(script_path, encoding="utf-8") as f:
        script_text = f.read()
    with open(expected_path, encoding="utf-8") as f:
        expected_output = f.read()

    actual_output = run_script(script_text)

    assert actual_output.strip() == expected_output.strip()
