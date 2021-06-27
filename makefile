VENV ?= .venv
PYTHON ?= python3.9
TESTS ?= tests
CODE ?= di
ALL = $(CODE) $(TESTS)
JOBS ?= 4

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install poetry
	$(VENV)/bin/poetry install

lint:
	$(VENV)/bin/black --skip-string-normalization --check $(ALL)
	$(VENV)/bin/flake8 --jobs $(JOBS) --statistics --show-source $(ALL)
	$(VENV)/bin/mypy $(ALL)

pretty:
	$(VENV)/bin/isort $(ALL)
	$(VENV)/bin/black --skip-string-normalization $(ALL)
