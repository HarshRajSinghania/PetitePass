.PHONY: help setup install-requirements install-dev run test smoke lint typecheck check build install uninstall clean

# `make` with no target prints the help below.
.DEFAULT_GOAL := help

help: ## Show this help
	@echo "PetitePass — available targets:"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Create the .venv virtualenv
	python3 -m venv .venv

install-requirements: ## Install runtime dependencies
	pip3 install -r requirements.txt

install-dev: ## Install dev dependencies (lint, types, tests, build)
	pip3 install -r requirements-dev.txt

run: ## Launch the GUI (from the source tree, no install needed)
	PYTHONPATH=src python3 -m petitepass.app

install: ## Install the app and the `petitepass` console script
	pip3 install .

uninstall: ## Uninstall the app
	pip3 uninstall -y petitepass

test: ## Run the pytest suite (real SQLCipher)
	python3 -m pytest tests -q

smoke: ## Run the headless GUI smoke test (offscreen)
	QT_QPA_PLATFORM=offscreen python3 tests/smoke_gui.py

lint: ## Lint with ruff
	ruff check src tests

typecheck: ## Type-check core with mypy
	mypy

check: lint typecheck test smoke ## Run lint, typecheck, tests, and smoke

# Standalone single-file binary (no Python required at runtime). Requires the
# dev dependencies (PyInstaller); run `make install-dev` first. --windowed so a
# GUI app does not spawn a console window.
build: ## Build a standalone single-file binary (PyInstaller)
	pyinstaller --onefile --windowed --name petitepass \
		--add-data "src/petitepass/core/data/10k-most-common.txt:petitepass/core/data" \
		src/petitepass/app.py

clean: ## Remove build artifacts
	rm -rf build dist *.spec __pycache__
