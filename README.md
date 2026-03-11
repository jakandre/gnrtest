# gnrtest

Static analyzer for [Genropy](https://www.genropy.org/) projects. Detects errors in models and views **without requiring Genropy runtime**.

## Features

- Pure static analysis using Python AST - no Genropy installation needed
- Validates model definitions (relations, formulas, columns)
- Validates view definitions (fieldcells, fields, table handlers)
- Supports `one_one` inverse relations
- Colored terminal output
- JSON output for CI/CD integration

## Installation

### Via pip (recommended)

```bash
pip install gnrtest
```

### From source

```bash
git clone https://github.com/jakandre/gnrtest.git
cd gnrtest
pip install -e .
```

## Usage

```bash
# Test current directory
gnrtest

# Test specific project
gnrtest /path/to/genropy/project

# Test specific packages
gnrtest -p mypackage
gnrtest -p pkg1 -p pkg2

# Test only models or views
gnrtest --models
gnrtest --views

# Verbose output (shows each error as found)
gnrtest -v

# JSON output (for CI/CD)
gnrtest --json
```

## Error Codes

### Model Errors (MODEL_001-015)

| Code | Description |
|------|-------------|
| MODEL_001 | formulaColumn references non-existing column |
| MODEL_002 | Relation to non-existing table |
| MODEL_003 | Relation to non-existing column |
| MODEL_004 | aliasColumn with invalid path |
| MODEL_005 | Formula SQL syntax error |
| MODEL_006 | FK/PK size mismatch (warning) |
| MODEL_007 | Missing primary key |
| MODEL_008 | Duplicate column names |
| MODEL_009 | Circular relations (warning) |
| MODEL_010 | FK/PK dtype mismatch |
| MODEL_011 | pyColumn without method |
| MODEL_012 | Trigger calls missing method |
| MODEL_013 | validate_min > validate_max |
| MODEL_014 | validate_len > size |
| MODEL_015 | Invalid import |

### View Errors (VIEW_001-012)

| Code | Description |
|------|-------------|
| VIEW_001 | fieldcell with non-existing column |
| VIEW_002 | fieldcell with invalid relation |
| VIEW_003 | field with non-existing column |
| VIEW_004 | th_* without corresponding table |
| VIEW_005 | Non-existing caption_field |
| VIEW_006 | Invalid deep relation path |
| VIEW_007 | TableHandler relation missing @ |
| VIEW_008 | viewResource/formResource not found |
| VIEW_009 | Invalid condition syntax (warning) |
| VIEW_010 | Invalid import |
| VIEW_011 | Missing View/Form class (warning) |
| VIEW_012 | Empty th_struct (warning) |

## Example Output

```
gnrtest - Genropy Static Analyzer
==================================================
Project: /path/to/project
Packages: mypackage

[PKG] Package: mypackage
   ✓ OK

==================================================
Summary: ✓ All checks passed!
```

With errors:

```
gnrtest - Genropy Static Analyzer
==================================================

[PKG] Package: mypackage
   ✗ 2 errors

==================================================

ERRORS (2)
------------------------------
MODEL_001 | model/invoice.py:45
  formulaColumn 'total' references non-existing column: $subtotal

VIEW_001 | resources/tables/invoice/th_invoice.py:23
  fieldcell references non-existing column: 'data_emissione'

==================================================
Summary: ✗ 2 error(s), 0 warning(s)
```

## Smart Features

### System Package Detection
Relations to standard Genropy packages (`adm`, `sys`, `gnr`, etc.) are automatically skipped.

### Specialized Base Classes
Tables extending `AttachmentTable`, `GnrDboTable`, etc. are handled correctly.

### Inverse Relations (one_one)
Supports `one_one='relation_name'` parameter for inverse relation navigation.

```python
# In sentenza.py
tbl.column('causa_id').relation('causa.id', one_one='sentenza')

# gnrtest correctly validates @sentenza.* access from causa table
```

### sysFields Detection
Tables using `self.sysFields(tbl)` automatically have system columns (`id`, `__mod_ts`, etc.) recognized.

## CI/CD Integration

```bash
# Exit code 0 = no errors, 1 = errors found
gnrtest --json > report.json || echo "Errors found"
```

## Contributing

Pull requests welcome! Please ensure tests pass before submitting.

## License

MIT License - see [LICENSE](LICENSE) file.
