# Runs the full test suite: unit tests (tests/test_suite.py) and the
# script-driven integration tests (tests/integration/test_text_scripts.py).
python -m pytest tests/ --cov=. --cov-report=term-missing --cov-report=html @args
