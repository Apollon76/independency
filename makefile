.PHONY : venv black flake9 mypy pylint lint pretty tests

TESTS ?= tests
CODE ?= independency
ALL = $(CODE) $(TESTS)
JOBS ?= 4

venv:
	uv sync --all-extras

black:
	uv run black --skip-string-normalization --check $(ALL)

flake8:
	uv run flake8 --jobs $(JOBS) --statistics --show-source $(ALL)

mypy:
	uv run mypy $(ALL)

pylint:
	uv run pylint --rcfile=setup.cfg $(CODE)

lint: black flake8 mypy pylint

pretty:
	uv run isort $(ALL)
	uv run black --skip-string-normalization $(ALL)

tests:
	uv run pytest --cov=independency $(TESTS)
