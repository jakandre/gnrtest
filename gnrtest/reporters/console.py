#!/usr/bin/env python
# encoding: utf-8
"""
Console reporter for gnrtest

Provides colorful terminal output for validation results.
"""
import sys
import json
from typing import List
from ..validators.base import ValidationError, ValidationResult
from ..core.error_catalog import Severity


class Colors:
    """ANSI color codes"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

    @classmethod
    def disable(cls):
        """Disable colors"""
        cls.RED = ''
        cls.GREEN = ''
        cls.YELLOW = ''
        cls.BLUE = ''
        cls.MAGENTA = ''
        cls.CYAN = ''
        cls.BOLD = ''
        cls.DIM = ''
        cls.RESET = ''


class ConsoleReporter:
    """Reporter that outputs to console with colors"""

    def __init__(self, verbose: bool = False, no_color: bool = False):
        self.verbose = verbose
        if no_color or not sys.stdout.isatty():
            Colors.disable()

    def report_start(self, project_path: str, packages: List[str]) -> None:
        """Report validation start"""
        print()
        print(f"{Colors.BOLD}{Colors.CYAN}gnrtest - Genropy Static Analyzer{Colors.RESET}")
        print(f"{Colors.DIM}{'=' * 50}{Colors.RESET}")
        print(f"Project: {project_path}")
        if packages:
            print(f"Packages: {', '.join(packages)}")
        print()

    def report_package_start(self, package: str) -> None:
        """Report package validation start"""
        icon = "📦" if sys.stdout.isatty() else "[PKG]"
        print(f"{icon} Package: {Colors.BOLD}{package}{Colors.RESET}")

    def report_package_progress(self, tables: int, views: int) -> None:
        """Report progress"""
        if self.verbose:
            check = f"{Colors.GREEN}✓{Colors.RESET}" if sys.stdout.isatty() else "[OK]"
            print(f"   Models: {check} {tables} tables")
            print(f"   Views:  {check} {views} resources")

    def report_error(self, error: ValidationError) -> None:
        """Report a single error"""
        if not self.verbose:
            return

        if error.is_error:
            color = Colors.RED
            icon = "✗" if sys.stdout.isatty() else "[ERR]"
        else:
            color = Colors.YELLOW
            icon = "⚠" if sys.stdout.isatty() else "[WRN]"

        code = f"{Colors.BOLD}{error.code}{Colors.RESET}"
        location = f"{Colors.DIM}{error.file_path}:{error.line_number}{Colors.RESET}"

        print(f"   {color}{icon}{Colors.RESET} {code} | {location}")
        print(f"      {error.message}")

    def report_package_complete(self, result: ValidationResult) -> None:
        """Report package completion"""
        if not self.verbose:
            if result.has_errors:
                status = f"{Colors.RED}✗ {result.error_count} errors{Colors.RESET}"
            elif result.has_warnings:
                status = f"{Colors.YELLOW}⚠ {result.warning_count} warnings{Colors.RESET}"
            else:
                status = f"{Colors.GREEN}✓ OK{Colors.RESET}"
            print(f"   {status}")
        print()

    def report_summary(self, results: List[ValidationResult]) -> None:
        """Report final summary"""
        print(f"{Colors.DIM}{'=' * 50}{Colors.RESET}")
        print()

        # Collect all errors
        all_errors = []
        for result in results:
            all_errors.extend(result.errors)

        errors = [e for e in all_errors if e.is_error]
        warnings = [e for e in all_errors if e.is_warning]

        # Print errors
        if errors:
            header = f"❌ ERRORS ({len(errors)})" if sys.stdout.isatty() else f"ERRORS ({len(errors)})"
            print(f"{Colors.BOLD}{Colors.RED}{header}{Colors.RESET}")
            print(f"{Colors.DIM}{'-' * 30}{Colors.RESET}")

            for error in errors:
                code = f"{Colors.BOLD}{error.code}{Colors.RESET}"
                location = f"{error.file_path}:{error.line_number}"
                print(f"{code} | {location}")
                print(f"  {error.message}")
            print()

        # Print warnings
        if warnings:
            header = f"⚠️  WARNINGS ({len(warnings)})" if sys.stdout.isatty() else f"WARNINGS ({len(warnings)})"
            print(f"{Colors.BOLD}{Colors.YELLOW}{header}{Colors.RESET}")
            print(f"{Colors.DIM}{'-' * 30}{Colors.RESET}")

            for warning in warnings:
                code = f"{Colors.BOLD}{warning.code}{Colors.RESET}"
                location = f"{warning.file_path}:{warning.line_number}"
                print(f"{code} | {location}")
                print(f"  {warning.message}")
            print()

        # Summary
        print(f"{Colors.DIM}{'=' * 50}{Colors.RESET}")

        total_errors = len(errors)
        total_warnings = len(warnings)

        if total_errors == 0 and total_warnings == 0:
            summary = f"{Colors.BOLD}{Colors.GREEN}✓ All checks passed!{Colors.RESET}"
            exit_code = 0
        elif total_errors == 0:
            summary = f"{Colors.BOLD}{Colors.YELLOW}⚠ {total_warnings} warning(s){Colors.RESET}"
            exit_code = 0  # Warnings don't fail
        else:
            summary = f"{Colors.BOLD}{Colors.RED}✗ {total_errors} error(s), {total_warnings} warning(s){Colors.RESET}"
            exit_code = 1

        print(f"Summary: {summary}")
        print()

        return exit_code


class JsonReporter:
    """Reporter that outputs JSON"""

    def __init__(self):
        self._data = {
            'project': '',
            'packages': [],
            'errors': [],
            'summary': {}
        }

    def report_start(self, project_path: str, packages: List[str]) -> None:
        self._data['project'] = project_path
        self._data['packages'] = packages

    def report_package_start(self, package: str) -> None:
        pass

    def report_package_progress(self, tables: int, views: int) -> None:
        pass

    def report_error(self, error: ValidationError) -> None:
        self._data['errors'].append({
            'code': error.code,
            'severity': error.severity.value,
            'message': error.message,
            'file_path': error.file_path,
            'line_number': error.line_number,
            'package': error.package,
            'table': error.table
        })

    def report_package_complete(self, result: ValidationResult) -> None:
        pass

    def report_summary(self, results: List[ValidationResult]) -> int:
        total_errors = sum(r.error_count for r in results)
        total_warnings = sum(r.warning_count for r in results)

        self._data['summary'] = {
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'exit_code': 1 if total_errors > 0 else 0
        }

        print(json.dumps(self._data, indent=2))

        return self._data['summary']['exit_code']
