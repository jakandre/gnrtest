# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is gnrtest

A static analyzer for [Genropy](https://www.genropy.org/) projects. It uses Python AST to detect errors in model and view files **without requiring Genropy runtime**. Zero external dependencies.

## Commands

```bash
# Install for development
pip install -e .

# Run the analyzer
gnrtest                              # current directory
gnrtest /path/to/project             # specific project
gnrtest -p mypackage                 # specific package
gnrtest --models                     # models only
gnrtest --views                      # views only
gnrtest -v                           # verbose (show errors as found)
gnrtest --json                       # JSON output for CI

# Build distribution
python -m build
```

There are no tests yet. Python 3.8+ is required.

## Architecture

The pipeline follows: **Parse → Build Schema → Validate → Report**.

### Entry point
- `gnrtest/cli.py` — CLI argument parsing and orchestration via `run_validation()`. Finds the project root by looking for `packages/` dir or `main.py`.

### Analyzers (AST parsing)
- `analyzers/model_parser.py` — Parses Genropy model files (`model/*.py`) using `ast`. Extracts `TableDef` with columns, relations, methods. Looks for the `Table` class and its `config_db` method. Handles `sysFields()` auto-columns and special column types (formulaColumn, aliasColumn, pyColumn).
- `analyzers/view_parser.py` — Parses view files (`resources/tables/th_*.py`). Extracts `ViewFileDef` with fieldcells, fields, table handlers, and resource classes.

### Schema
- `core/schema_builder.py` — `SchemaBuilder` converts parsed `TableDef`s into a `Schema` (dict of `SchemaTable` keyed by `pkg.table`). Also builds inverse relations from `one_one` parameters. `Schema.resolve_relation_path()` walks `@rel1.@rel2.column` paths for validation.

### Validators
- `validators/base.py` — `BaseValidator` ABC and `ValidationError`/`ValidationResult` dataclasses. Validators call `self.add_error(ErrorCatalog.CODE, ...)` to emit errors.
- `validators/model_validators.py` — `AllModelValidators` runs: FormulaValidator, RelationValidator, AliasColumnValidator, PrimaryKeyValidator, PyColumnValidator, ValidationRulesValidator. System packages (`adm`, `sys`, `gnr`, etc.) are auto-skipped for relation validation.
- `validators/view_validators.py` — `AllViewValidators` runs: FieldcellColumnValidator, FieldcellRelationValidator, FormFieldValidator, ViewTableExistsValidator, CaptionFieldValidator, TableHandlerRelationValidator, ResourceExistsValidator, ViewClassValidator, ThStructValidator.

### Error catalog
- `core/error_catalog.py` — All error codes (MODEL_001–015, VIEW_001–012) with severity (ERROR/WARNING) and message templates. Warnings don't cause non-zero exit.

### Reporters
- `reporters/console.py` — `ConsoleReporter` (colored terminal output) and `JsonReporter`. Colors auto-disable when not a TTY.

## Adding a new validator

1. Define the error code in `core/error_catalog.py` as an `ErrorCode` with code, severity, and message template.
2. Create a validator class in the appropriate `*_validators.py`, extending `BaseValidator`.
3. Register it in `AllModelValidators` or `AllViewValidators`.

## Genropy concepts relevant to this code

- **Packages**: contain `model/` (table definitions) and `resources/tables/` (view definitions)
- **Tables**: defined in `model/*.py` with a `Table` class containing `config_db()`
- **Relations**: `tbl.column('x').relation('pkg.table.col', one_one='inverse_name')`
- **Views**: `th_<tablename>.py` files with View/Form classes containing `th_struct` (fieldcells) and table handlers
