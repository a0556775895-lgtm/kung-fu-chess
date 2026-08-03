"""Run every `.kfc` script in this directory's scripts folder through the
real text-scenario runner and compare stdout against its
sibling `.expected` file.

Each `.kfc` uses the same `Board:`/`Commands:` DSL described in the
README (click/jump/wait/print board); each `.expected` holds the exact
text those commands should print.
"""

from pathlib import Path

import pytest

from DOCS.tests.texttests.script_runner import run_script

SCRIPTS_DIR = Path(__file__).with_name("scripts")

SCRIPT_NAMES = sorted(
    path.name for path in SCRIPTS_DIR.glob("*.kfc")
)


@pytest.mark.parametrize("script_name", SCRIPT_NAMES)
def test_script_output_matches_expected(script_name):
    script_path = SCRIPTS_DIR / script_name
    expected_path = script_path.with_suffix(".expected")

    with script_path.open(encoding="utf-8") as f:
        script_text = f.read()
    with expected_path.open(encoding="utf-8") as f:
        expected_output = f.read()

    actual_output = run_script(script_text)

    assert actual_output.strip() == expected_output.strip()
