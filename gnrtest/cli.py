#!/usr/bin/env python
# encoding: utf-8
"""
gnrtest - Static analyzer for Genropy projects

Usage:
    gnrtest [project_path] [options]
    gnrtest --help

Examples:
    gnrtest                           # Test current directory
    gnrtest /path/to/project          # Test specific project
    gnrtest -p mypackage              # Test specific package
    gnrtest --verbose                 # Verbose output
    gnrtest --json                    # JSON output
"""
import os
import sys
import argparse
from typing import List, Optional

from .core.schema_builder import SchemaBuilder
from .analyzers.view_parser import ViewParser
from .validators.model_validators import AllModelValidators
from .validators.view_validators import AllViewValidators
from .validators.base import ValidationResult
from .reporters.console import ConsoleReporter, JsonReporter


def find_project_root(start_path: str) -> Optional[str]:
    """
    Find the Genropy project root directory.

    Looks for packages/ directory or main.py (single package).
    """
    current = os.path.abspath(start_path)

    # Check if it's a project root
    if os.path.isdir(os.path.join(current, 'packages')):
        return current

    # Check if it's a single package
    if os.path.isfile(os.path.join(current, 'main.py')):
        return current

    # Walk up looking for packages/
    while current != '/':
        packages_dir = os.path.join(current, 'packages')
        if os.path.isdir(packages_dir):
            return current
        current = os.path.dirname(current)

    return None


def find_packages(project_path: str) -> List[str]:
    """Find all packages in a project"""
    packages_dir = os.path.join(project_path, 'packages')

    if not os.path.isdir(packages_dir):
        # Single package mode
        if os.path.isfile(os.path.join(project_path, 'main.py')):
            return [os.path.basename(project_path)]
        return []

    packages = []
    for name in os.listdir(packages_dir):
        pkg_path = os.path.join(packages_dir, name)
        if os.path.isdir(pkg_path) and not name.startswith('_') and not name.startswith('.'):
            # Check if it's a valid package (has main.py or model/)
            if os.path.isfile(os.path.join(pkg_path, 'main.py')) or \
               os.path.isdir(os.path.join(pkg_path, 'model')):
                packages.append(name)

    return sorted(packages)


def get_package_path(project_path: str, package_name: str) -> str:
    """Get the path to a package"""
    packages_dir = os.path.join(project_path, 'packages')
    if os.path.isdir(packages_dir):
        return os.path.join(packages_dir, package_name)
    return project_path


def run_validation(
    project_path: str,
    packages: List[str] = None,
    test_models: bool = True,
    test_views: bool = True,
    verbose: bool = False,
    json_output: bool = False,
    no_color: bool = False
) -> int:
    """
    Run validation on a project.

    Returns:
        Exit code (0=ok, 1=errors)
    """
    # Setup reporter
    if json_output:
        reporter = JsonReporter()
    else:
        reporter = ConsoleReporter(verbose=verbose, no_color=no_color)

    # Find packages
    if not packages:
        packages = find_packages(project_path)

    if not packages:
        print(f"Error: No packages found in {project_path}", file=sys.stderr)
        return 1

    reporter.report_start(project_path, packages)

    # Build schema
    builder = SchemaBuilder()
    schema = builder.build_from_project(project_path, packages)

    # Parse views
    view_parser = ViewParser()

    results = []

    for package in packages:
        reporter.report_package_start(package)

        pkg_path = get_package_path(project_path, package)
        result = ValidationResult(package=package)

        # Count tables
        result.tables_checked = len(schema.get_package_tables(package))

        # Run model validators
        if test_models:
            model_validators = AllModelValidators(schema)
            model_errors = model_validators.validate(package)
            for error in model_errors:
                result.errors.append(error)
                reporter.report_error(error)

        # Parse and validate views
        if test_views:
            views = view_parser.parse_package_views(pkg_path, package)
            result.views_checked = len(views)

            view_validators = AllViewValidators(schema, views)
            view_errors = view_validators.validate(package)
            for error in view_errors:
                result.errors.append(error)
                reporter.report_error(error)

        reporter.report_package_progress(result.tables_checked, result.views_checked)
        reporter.report_package_complete(result)
        results.append(result)

    return reporter.report_summary(results)


def main(args: List[str] = None) -> int:
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='gnrtest - Static analyzer for Genropy projects',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  gnrtest                           Test current directory
  gnrtest /path/to/project          Test specific project
  gnrtest -p mypackage              Test only specific package
  gnrtest -p pkg1 -p pkg2           Test multiple packages
  gnrtest --models                  Test only models
  gnrtest --views                   Test only views
  gnrtest -v                        Verbose output
  gnrtest --json                    JSON output
"""
    )

    parser.add_argument(
        'project_path',
        nargs='?',
        default='.',
        help='Path to Genropy project (default: current directory)'
    )

    parser.add_argument(
        '-p', '--package',
        action='append',
        dest='packages',
        metavar='PKG',
        help='Package to test (can be repeated)'
    )

    parser.add_argument(
        '--models',
        action='store_true',
        help='Only test models'
    )

    parser.add_argument(
        '--views',
        action='store_true',
        help='Only test views'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )

    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='gnrtest 0.1.0'
    )

    parsed = parser.parse_args(args)

    # Find project root
    project_path = find_project_root(parsed.project_path)
    if not project_path:
        print(f"Error: Could not find Genropy project at '{parsed.project_path}'", file=sys.stderr)
        print("Make sure you're in a directory with 'packages/' or a single package with 'main.py'", file=sys.stderr)
        return 1

    # Determine what to test
    test_models = True
    test_views = True
    if parsed.models and not parsed.views:
        test_views = False
    elif parsed.views and not parsed.models:
        test_models = False

    return run_validation(
        project_path=project_path,
        packages=parsed.packages,
        test_models=test_models,
        test_views=test_views,
        verbose=parsed.verbose,
        json_output=parsed.json,
        no_color=parsed.no_color
    )


if __name__ == '__main__':
    sys.exit(main())
