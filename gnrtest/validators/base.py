#!/usr/bin/env python
# encoding: utf-8
"""
Base validator classes for gnrtest
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from ..core.error_catalog import ErrorCode, Severity, ErrorCatalog


@dataclass
class ValidationError:
    """A single validation error or warning"""
    code: str
    severity: Severity
    message: str
    file_path: str
    line_number: int = 0
    package: str = ''
    table: str = ''
    context: Dict[str, Any] = field(default_factory=dict)

    def __str__(self):
        loc = f"{self.file_path}"
        if self.line_number:
            loc += f":{self.line_number}"
        return f"[{self.code}] {loc}: {self.message}"

    @property
    def is_error(self) -> bool:
        return self.severity == Severity.ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity == Severity.WARNING


@dataclass
class ValidationResult:
    """Result of validating a package"""
    package: str
    errors: List[ValidationError] = field(default_factory=list)
    tables_checked: int = 0
    views_checked: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for e in self.errors if e.is_error)

    @property
    def warning_count(self) -> int:
        return sum(1 for e in self.errors if e.is_warning)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    @property
    def has_warnings(self) -> bool:
        return self.warning_count > 0


class BaseValidator(ABC):
    """Abstract base class for validators"""

    def __init__(self, schema):
        """
        Initialize validator.

        Args:
            schema: Schema instance for lookups
        """
        self.schema = schema
        self._errors: List[ValidationError] = []

    @abstractmethod
    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        """Run validation for a package"""
        pass

    def add_error(
        self,
        error_code: ErrorCode,
        file_path: str,
        line_number: int = 0,
        package: str = '',
        table: str = '',
        **format_kwargs
    ) -> ValidationError:
        """Add a validation error"""
        # Include table and package in format_kwargs for message formatting
        all_kwargs = {'table': table, 'package': package, **format_kwargs}
        error = ValidationError(
            code=error_code.code,
            severity=error_code.severity,
            message=error_code.format_message(**all_kwargs),
            file_path=file_path,
            line_number=line_number,
            package=package,
            table=table,
            context=format_kwargs
        )
        self._errors.append(error)
        return error

    def clear_errors(self) -> None:
        """Clear all collected errors"""
        self._errors = []

    def get_errors(self) -> List[ValidationError]:
        """Get all collected errors"""
        return self._errors.copy()
