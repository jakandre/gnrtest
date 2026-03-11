#!/usr/bin/env python
# encoding: utf-8
"""
Error catalog for gnrtest

Defines all error codes and their messages.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class Severity(Enum):
    """Error severity levels"""
    ERROR = 'error'
    WARNING = 'warning'


@dataclass
class ErrorCode:
    """Definition of an error code"""
    code: str
    severity: Severity
    message_template: str
    description: str = ''

    def format_message(self, **kwargs) -> str:
        """Format the message with provided arguments"""
        try:
            return self.message_template.format(**kwargs)
        except KeyError:
            return self.message_template


class ErrorCatalog:
    """
    Catalog of all validation error codes.

    Error codes follow the pattern:
    - MODEL_xxx: Model validation errors
    - VIEW_xxx: View validation errors
    """

    # ==================== MODEL ERRORS ====================

    MODEL_001 = ErrorCode(
        code='MODEL_001',
        severity=Severity.ERROR,
        message_template="formulaColumn '{formula_column}' references non-existing column: ${column}",
        description="Column reference in formula does not exist"
    )

    MODEL_002 = ErrorCode(
        code='MODEL_002',
        severity=Severity.ERROR,
        message_template="Column '{column}' has relation to non-existing table: {target_table}",
        description="Relation target table does not exist"
    )

    MODEL_003 = ErrorCode(
        code='MODEL_003',
        severity=Severity.ERROR,
        message_template="Column '{column}' has relation to non-existing column: {target_table}.{target_column}",
        description="Relation target column does not exist"
    )

    MODEL_004 = ErrorCode(
        code='MODEL_004',
        severity=Severity.ERROR,
        message_template="aliasColumn '{alias_column}' has invalid path: {path} ({error})",
        description="Alias column relation path is invalid"
    )

    MODEL_005 = ErrorCode(
        code='MODEL_005',
        severity=Severity.ERROR,
        message_template="Formula has SQL syntax error: {error}",
        description="Formula contains SQL syntax errors"
    )

    MODEL_006 = ErrorCode(
        code='MODEL_006',
        severity=Severity.WARNING,
        message_template="FK '{column}' size ({fk_size}) differs from PK size ({pk_size})",
        description="Foreign key size doesn't match primary key size"
    )

    MODEL_007 = ErrorCode(
        code='MODEL_007',
        severity=Severity.ERROR,
        message_template="Table '{table}' has no primary key defined",
        description="Table is missing pkey attribute"
    )

    MODEL_008 = ErrorCode(
        code='MODEL_008',
        severity=Severity.ERROR,
        message_template="Duplicate column '{column}' (first defined at line {first_line})",
        description="Column name is defined multiple times"
    )

    MODEL_009 = ErrorCode(
        code='MODEL_009',
        severity=Severity.WARNING,
        message_template="Circular relation detected: {cycle}",
        description="Tables have circular foreign key dependencies"
    )

    MODEL_010 = ErrorCode(
        code='MODEL_010',
        severity=Severity.ERROR,
        message_template="FK '{column}' dtype ({fk_dtype}) doesn't match PK dtype ({pk_dtype})",
        description="Foreign key data type doesn't match primary key"
    )

    MODEL_011 = ErrorCode(
        code='MODEL_011',
        severity=Severity.ERROR,
        message_template="pyColumn '{py_column}' references missing method: {method}",
        description="pyColumn py_method does not exist in Table class"
    )

    MODEL_012 = ErrorCode(
        code='MODEL_012',
        severity=Severity.ERROR,
        message_template="Trigger '{trigger}' calls non-existing method: {method}",
        description="Trigger method calls undefined method"
    )

    MODEL_013 = ErrorCode(
        code='MODEL_013',
        severity=Severity.ERROR,
        message_template="Column '{column}' has validate_min ({min_value}) > validate_max ({max_value})",
        description="Validation min is greater than max"
    )

    MODEL_014 = ErrorCode(
        code='MODEL_014',
        severity=Severity.ERROR,
        message_template="Column '{column}' has validate_len ({validate_len}) > size ({size})",
        description="Validation length exceeds column size"
    )

    MODEL_015 = ErrorCode(
        code='MODEL_015',
        severity=Severity.ERROR,
        message_template="Import error in model: {import_stmt}",
        description="Model file has invalid import"
    )

    # ==================== VIEW ERRORS ====================

    VIEW_001 = ErrorCode(
        code='VIEW_001',
        severity=Severity.ERROR,
        message_template="fieldcell references non-existing column: '{field}'",
        description="fieldcell field does not exist in table"
    )

    VIEW_002 = ErrorCode(
        code='VIEW_002',
        severity=Severity.ERROR,
        message_template="fieldcell has invalid relation path: '{field}' ({error})",
        description="fieldcell relation path is invalid"
    )

    VIEW_003 = ErrorCode(
        code='VIEW_003',
        severity=Severity.ERROR,
        message_template="field references non-existing column: '{field}'",
        description="Form field does not exist in table"
    )

    VIEW_004 = ErrorCode(
        code='VIEW_004',
        severity=Severity.ERROR,
        message_template="Resource '{resource}' has no corresponding table: {table}",
        description="th_* file exists but table does not"
    )

    VIEW_005 = ErrorCode(
        code='VIEW_005',
        severity=Severity.ERROR,
        message_template="Table '{table}' has non-existing caption_field: '{caption_field}'",
        description="caption_field column does not exist"
    )

    VIEW_006 = ErrorCode(
        code='VIEW_006',
        severity=Severity.ERROR,
        message_template="Deep relation path is invalid: '{path}' ({error})",
        description="Multi-level relation path has errors"
    )

    VIEW_007 = ErrorCode(
        code='VIEW_007',
        severity=Severity.ERROR,
        message_template="TableHandler relation missing '@': relation='{relation}' (should be '{suggestion}')",
        description="dialogTableHandler/inlineTableHandler relation should start with @"
    )

    VIEW_008 = ErrorCode(
        code='VIEW_008',
        severity=Severity.ERROR,
        message_template="{resource_type} '{resource}' not found for table '{table}'",
        description="Referenced viewResource or formResource does not exist"
    )

    VIEW_009 = ErrorCode(
        code='VIEW_009',
        severity=Severity.WARNING,
        message_template="Condition has suspicious syntax: '{condition}' ({error})",
        description="TableHandler condition may have syntax issues"
    )

    VIEW_010 = ErrorCode(
        code='VIEW_010',
        severity=Severity.ERROR,
        message_template="Import error in view: {import_stmt}",
        description="View file has invalid import"
    )

    VIEW_011 = ErrorCode(
        code='VIEW_011',
        severity=Severity.WARNING,
        message_template="Resource '{resource}' has no View or Form class defined",
        description="th_*.py file missing View/Form class"
    )

    VIEW_012 = ErrorCode(
        code='VIEW_012',
        severity=Severity.WARNING,
        message_template="th_struct in '{resource}' defines no fieldcells",
        description="th_struct method is empty or has no fieldcells"
    )

    @classmethod
    def get_by_code(cls, code: str) -> Optional[ErrorCode]:
        """Get ErrorCode by its code string"""
        for name in dir(cls):
            if name.startswith('MODEL_') or name.startswith('VIEW_'):
                error = getattr(cls, name)
                if isinstance(error, ErrorCode) and error.code == code:
                    return error
        return None

    @classmethod
    def get_all_codes(cls) -> list:
        """Get all error codes"""
        codes = []
        for name in dir(cls):
            if name.startswith('MODEL_') or name.startswith('VIEW_'):
                error = getattr(cls, name)
                if isinstance(error, ErrorCode):
                    codes.append(error)
        return codes
