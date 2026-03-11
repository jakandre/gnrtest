#!/usr/bin/env python
# encoding: utf-8
"""
Model validators for gnrtest

Validates Genropy model definitions (MODEL_001-015).
"""
from typing import List, Dict, Set
from .base import BaseValidator, ValidationError
from ..core.error_catalog import ErrorCatalog
from ..core.schema_builder import Schema
from ..analyzers.model_parser import ModelParser


class FormulaValidator(BaseValidator):
    """Validates formulaColumn references (MODEL_001, MODEL_005)"""

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for table_name in self.schema.get_package_tables(package):
            table = self.schema.get_table(f"{package}.{table_name}")
            if not table:
                continue

            for col_name, col in table.columns.items():
                if col.column_type == 'formulaColumn' and col.formula:
                    self._validate_formula(table, col)

        return self.get_errors()

    def _validate_formula(self, table, col) -> None:
        """Validate a formula"""
        formula = col.formula

        # MODEL_005: Check syntax
        if formula.count('(') != formula.count(')'):
            self.add_error(
                ErrorCatalog.MODEL_005,
                table.file_path,
                col.line_number,
                package=table.package,
                table=table.name,
                error="Unbalanced parentheses"
            )

        # MODEL_001: Check column references
        refs = ModelParser.extract_formula_refs(formula)
        for col_ref in refs['columns']:
            if not self.schema.column_exists(table.fullname, col_ref):
                self.add_error(
                    ErrorCatalog.MODEL_001,
                    table.file_path,
                    col.line_number,
                    package=table.package,
                    table=table.name,
                    formula_column=col.name,
                    column=col_ref
                )


class RelationValidator(BaseValidator):
    """Validates relation definitions (MODEL_002, MODEL_003)"""

    # Known Genropy system packages that are not part of user projects
    SYSTEM_PACKAGES = {'adm', 'sys', 'gnr', 'gnrcore', 'email', 'biz'}

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for table_name in self.schema.get_package_tables(package):
            table = self.schema.get_table(f"{package}.{table_name}")
            if not table:
                continue

            for rel_name, rel in table.relations.items():
                self._validate_relation(table, rel)

        return self.get_errors()

    def _validate_relation(self, table, rel) -> None:
        """Validate a relation"""
        target_fullname = rel.target_fullname
        if not rel.target_package:
            target_fullname = f"{table.package}.{rel.target_table}"

        # Skip validation for relations to system packages
        target_pkg = rel.target_package or table.package
        if target_pkg in self.SYSTEM_PACKAGES:
            return

        # MODEL_002: Check target table exists
        target_table = self.schema.get_table(target_fullname)
        if not target_table:
            self.add_error(
                ErrorCatalog.MODEL_002,
                table.file_path,
                rel.line_number,
                package=table.package,
                column=rel.column_name,
                target_table=target_fullname
            )
            return

        # MODEL_003: Check target column exists
        if not self.schema.column_exists(target_fullname, rel.target_column):
            self.add_error(
                ErrorCatalog.MODEL_003,
                table.file_path,
                rel.line_number,
                package=table.package,
                column=rel.column_name,
                target_table=target_fullname,
                target_column=rel.target_column
            )


class AliasColumnValidator(BaseValidator):
    """Validates aliasColumn paths (MODEL_004)"""

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for table_name in self.schema.get_package_tables(package):
            table = self.schema.get_table(f"{package}.{table_name}")
            if not table:
                continue

            for col_name, col in table.columns.items():
                if col.column_type == 'aliasColumn' and col.relation_path:
                    self._validate_alias(table, col)

        return self.get_errors()

    def _validate_alias(self, table, col) -> None:
        """Validate an alias column path"""
        resolved = self.schema.resolve_relation_path(table.fullname, col.relation_path)
        if not resolved.valid:
            self.add_error(
                ErrorCatalog.MODEL_004,
                table.file_path,
                col.line_number,
                package=table.package,
                table=table.name,
                alias_column=col.name,
                path=col.relation_path,
                error=resolved.error
            )


class PrimaryKeyValidator(BaseValidator):
    """Validates primary key existence (MODEL_007)"""

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for table_name in self.schema.get_package_tables(package):
            table = self.schema.get_table(f"{package}.{table_name}")
            if not table:
                continue

            # Skip tables with specialized base classes (they define their own pkey)
            if table.has_specialized_base:
                continue

            if not table.pkey:
                self.add_error(
                    ErrorCatalog.MODEL_007,
                    table.file_path,
                    table.line_number,
                    package=table.package,
                    table=table.name
                )

        return self.get_errors()


class DuplicateColumnValidator(BaseValidator):
    """Validates no duplicate columns (MODEL_008)"""

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()
        # Duplicates are already handled by dict keys in schema
        # This would need raw parsing to detect
        return self.get_errors()


class PyColumnValidator(BaseValidator):
    """Validates pyColumn methods exist (MODEL_011)"""

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for table_name in self.schema.get_package_tables(package):
            table = self.schema.get_table(f"{package}.{table_name}")
            if not table:
                continue

            for col_name, col in table.columns.items():
                if col.column_type == 'pyColumn':
                    method_name = f"pyColumn_{col.py_method or col.name}"
                    if method_name not in table.methods:
                        self.add_error(
                            ErrorCatalog.MODEL_011,
                            table.file_path,
                            col.line_number,
                            package=table.package,
                            table=table.name,
                            py_column=col.name,
                            method=method_name
                        )

        return self.get_errors()


class ValidationRulesValidator(BaseValidator):
    """Validates validation rules (MODEL_013, MODEL_014)"""

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for table_name in self.schema.get_package_tables(package):
            table = self.schema.get_table(f"{package}.{table_name}")
            if not table:
                continue

            for col_name, col in table.columns.items():
                # MODEL_013: min > max
                if col.validate_min is not None and col.validate_max is not None:
                    try:
                        min_val = float(col.validate_min) if isinstance(col.validate_min, str) else col.validate_min
                        max_val = float(col.validate_max) if isinstance(col.validate_max, str) else col.validate_max
                        if min_val > max_val:
                            self.add_error(
                                ErrorCatalog.MODEL_013,
                                table.file_path,
                                col.line_number,
                                package=table.package,
                                column=col.name,
                                min_value=col.validate_min,
                                max_value=col.validate_max
                            )
                    except (ValueError, TypeError):
                        pass

                # MODEL_014: validate_len > size
                if col.validate_len is not None and col.size:
                    try:
                        size = self._parse_size(col.size)
                        validate_len = int(col.validate_len) if isinstance(col.validate_len, str) else col.validate_len
                        if validate_len > size:
                            self.add_error(
                                ErrorCatalog.MODEL_014,
                                table.file_path,
                                col.line_number,
                                package=table.package,
                                column=col.name,
                                size=size,
                                validate_len=col.validate_len
                            )
                    except ValueError:
                        pass

        return self.get_errors()

    def _parse_size(self, size_str: str) -> int:
        """Parse size string"""
        if ':' in size_str:
            return int(size_str.split(':')[-1])
        return int(size_str)


class AllModelValidators:
    """Runs all model validators"""

    def __init__(self, schema: Schema):
        self.validators = [
            FormulaValidator(schema),
            RelationValidator(schema),
            AliasColumnValidator(schema),
            PrimaryKeyValidator(schema),
            PyColumnValidator(schema),
            ValidationRulesValidator(schema),
        ]

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        """Run all validators"""
        errors = []
        for validator in self.validators:
            errors.extend(validator.validate(package, **kwargs))
        return errors
