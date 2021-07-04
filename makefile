.PHONY : venv black flake9 mypy pylint lint pretty tests

VENV ?= .venv
PYTHON ?= python3.9
TESTS ?= tests
CODE ?= independency
ALL = $(CODE) $(TESTS)
JOBS ?= 4

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install poetry
	$(VENV)/bin/poetry install

black:
	$(VENV)/bin/black --skip-string-normalization --check $(ALL)

flake8:
	$(VENV)/bin/flake8 --jobs $(JOBS) --statistics --show-source $(ALL)

mypy:
	$(VENV)/bin/mypy $(ALL)

pylint:
	$(VENV)/bin/pylint --jobs $(JOBS) --rcfile=setup.cfg $(CODE)

lint: black flake8 mypy pylint

pretty:
	$(VENV)/bin/isort $(ALL)
	$(VENV)/bin/black --skip-string-normalization $(ALL)

tests:
	$(VENV)/bin/pytest $(TESTS)
