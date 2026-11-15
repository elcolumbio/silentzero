# The source of truth for how to run anything in this repo.
.PHONY: help test cases check lint build clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-10s %s\n", $$1, $$2}'

test:  ## run the test suite (no network; fixtures are committed captures)
	uv run pytest tests/ -q

cases:  ## run the four real failures this library is named after
	uv run python -m silentzero cases

check: test  ## test, then compile-check every module
	uv run python -m compileall -q src/silentzero

build:  ## build the wheel and sdist
	uv build

clean:
	rm -rf dist build .pytest_cache src/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
