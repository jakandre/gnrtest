#!/usr/bin/env python
# encoding: utf-8
"""
Schema builder for gnrtest

Builds a complete schema from parsed model files.
Works without Genropy runtime.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from ..analyzers.model_parser import ModelParser, TableDef, ColumnDef, RelationDef


@dataclass
class SchemaColumn:
    """Column in the schema"""
    name: str
    dtype: Optional[str] = None
    size: Optional[str] = None
    column_type: str = 'column'
    formula: Optional[str] = None
    relation_path: Optional[str] = None
    py_method: Optional[str] = None
    line_number: int = 0
    # Validation attributes
    validate_min: Optional[float] = None
    validate_max: Optional[float] = None
    validate_len: Optional[int] = None


@dataclass
class SchemaRelation:
    """Relation in the schema"""
    column_name: str
    target_package: Optional[str]
    target_table: str
    target_column: str
    line_number: int = 0
    one_one: Optional[str] = None  # Inverse relation name on target
    relation_name: Optional[str] = None
    source_table: Optional[str] = None  # For inverse relations: where it comes from
    is_inverse: bool = False  # True if this is an inverse relation

    @property
    def target_fullname(self) -> str:
        """Get full target table name"""
        if self.target_package:
            return f"{self.target_package}.{self.target_table}"
        return self.target_table


@dataclass
class SchemaTable:
    """Table in the schema"""
    name: str
    package: str
    file_path: str
    pkey: Optional[str] = None
    caption_field: Optional[str] = None
    columns: Dict[str, SchemaColumn] = field(default_factory=dict)
    relations: Dict[str, SchemaRelation] = field(default_factory=dict)
    methods: Set[str] = field(default_factory=set)
    line_number: int = 0
    has_specialized_base: bool = False  # Extends AttachmentTable, etc.

    @property
    def fullname(self) -> str:
        """Get full table name (pkg.table)"""
        return f"{self.package}.{self.name}"


@dataclass
class ResolvedPath:
    """Result of resolving a relation path"""
    valid: bool
    final_table: Optional[str] = None
    final_column: Optional[str] = None
    error: Optional[str] = None
    steps: List[Tuple[str, str]] = field(default_factory=list)  # [(table, column), ...]


class Schema:
    """
    Complete schema built from model files.

    Provides lookups for tables, columns, and relations.
    """

    def __init__(self):
        self.tables: Dict[str, SchemaTable] = {}  # fullname -> table
        self._packages: Dict[str, Set[str]] = {}  # package -> set of table names

    def add_table(self, table: SchemaTable) -> None:
        """Add a table to the schema"""
        self.tables[table.fullname] = table
        if table.package not in self._packages:
            self._packages[table.package] = set()
        self._packages[table.package].add(table.name)

    def get_table(self, fullname: str) -> Optional[SchemaTable]:
        """Get table by fullname (pkg.table)"""
        return self.tables.get(fullname)

    def get_table_by_name(self, package: str, table_name: str) -> Optional[SchemaTable]:
        """Get table by package and name"""
        return self.tables.get(f"{package}.{table_name}")

    def get_package_tables(self, package: str) -> Set[str]:
        """Get all table names in a package"""
        return self._packages.get(package, set())

    def column_exists(self, table_fullname: str, column_name: str) -> bool:
        """Check if a column exists in a table"""
        table = self.get_table(table_fullname)
        if not table:
            return False
        return column_name in table.columns

    def get_column(self, table_fullname: str, column_name: str) -> Optional[SchemaColumn]:
        """Get a column from a table"""
        table = self.get_table(table_fullname)
        if not table:
            return None
        return table.columns.get(column_name)

    def get_relation(self, table_fullname: str, relation_name: str) -> Optional[SchemaRelation]:
        """Get a relation from a table"""
        table = self.get_table(table_fullname)
        if not table:
            return None
        return table.relations.get(relation_name)

    def resolve_relation_path(self, start_table: str, path: str) -> ResolvedPath:
        """
        Resolve a relation path like @rel1.@rel2.campo.

        Args:
            start_table: Starting table fullname (pkg.table)
            path: Relation path to resolve

        Returns:
            ResolvedPath with resolution results
        """
        if not path:
            return ResolvedPath(valid=False, error="Empty path")

        # Parse path parts
        path = path.lstrip('@')
        parts = path.replace('@', '').split('.')

        if not parts:
            return ResolvedPath(valid=False, error="Invalid path format")

        current_table = start_table
        steps = []

        # Process all parts except the last (relations)
        for i, part in enumerate(parts[:-1]):
            table = self.get_table(current_table)
            if not table:
                return ResolvedPath(
                    valid=False,
                    error=f"Table '{current_table}' not found",
                    steps=steps
                )

            # Find relation
            rel = table.relations.get(part)
            if not rel:
                # Check if it's a column name used as relation
                col = table.columns.get(part)
                if col:
                    rel = table.relations.get(part)

            if not rel:
                return ResolvedPath(
                    valid=False,
                    error=f"Relation '@{part}' not found in table '{current_table}'",
                    steps=steps
                )

            # Get target table
            target_fullname = rel.target_fullname
            if not rel.target_package:
                # Same package
                target_fullname = f"{table.package}.{rel.target_table}"

            steps.append((current_table, part))
            current_table = target_fullname

        # Last part is the final column
        final_column = parts[-1]
        final_table = self.get_table(current_table)

        if not final_table:
            return ResolvedPath(
                valid=False,
                error=f"Table '{current_table}' not found",
                steps=steps
            )

        if not self.column_exists(current_table, final_column):
            return ResolvedPath(
                valid=False,
                error=f"Column '{final_column}' not found in table '{current_table}'",
                steps=steps
            )

        return ResolvedPath(
            valid=True,
            final_table=current_table,
            final_column=final_column,
            steps=steps
        )


class SchemaBuilder:
    """
    Builds Schema from model files.

    Scans a Genropy project directory and extracts all model definitions.
    """

    def __init__(self):
        self.parser = ModelParser()
        self.schema = Schema()

    def build_from_project(self, project_path: str, packages: List[str] = None) -> Schema:
        """
        Build schema from a Genropy project.

        Args:
            project_path: Path to the project root
            packages: List of package names to process (None = auto-detect)

        Returns:
            Complete Schema
        """
        self.schema = Schema()

        # Find packages directory
        packages_path = os.path.join(project_path, 'packages')
        if not os.path.isdir(packages_path):
            # Maybe it's a single package
            if os.path.isfile(os.path.join(project_path, 'main.py')):
                pkg_name = os.path.basename(project_path)
                self._process_package(project_path, pkg_name)
            self._build_inverse_relations()
            return self.schema

        # Process each package
        if packages:
            pkg_list = packages
        else:
            pkg_list = [
                d for d in os.listdir(packages_path)
                if os.path.isdir(os.path.join(packages_path, d))
                and not d.startswith('_')
                and not d.startswith('.')
            ]

        for pkg_name in pkg_list:
            pkg_path = os.path.join(packages_path, pkg_name)
            if os.path.isdir(pkg_path):
                self._process_package(pkg_path, pkg_name)

        # Build inverse relations from one_one definitions
        self._build_inverse_relations()

        return self.schema

    def _process_package(self, pkg_path: str, pkg_name: str) -> None:
        """Process a single package"""
        tables = self.parser.parse_package(pkg_path, pkg_name)

        for table_def in tables:
            schema_table = self._convert_table(table_def)
            self.schema.add_table(schema_table)

    def _convert_table(self, table_def: TableDef) -> SchemaTable:
        """Convert TableDef to SchemaTable"""
        schema_table = SchemaTable(
            name=table_def.name,
            package=table_def.package,
            file_path=table_def.file_path,
            pkey=table_def.pkey,
            caption_field=table_def.caption_field,
            methods=table_def.methods,
            line_number=table_def.line_number,
            has_specialized_base=table_def.has_specialized_base
        )

        # Convert columns
        for col_def in table_def.columns:
            schema_col = SchemaColumn(
                name=col_def.name,
                dtype=col_def.dtype,
                size=col_def.size,
                column_type=col_def.column_type,
                formula=col_def.formula,
                relation_path=col_def.relation_path,
                py_method=col_def.py_method,
                line_number=col_def.line_number,
                validate_min=col_def.attributes.get('validate_min'),
                validate_max=col_def.attributes.get('validate_max'),
                validate_len=col_def.attributes.get('validate_len')
            )
            schema_table.columns[col_def.name] = schema_col

        # Convert relations
        for rel_def in table_def.relations:
            schema_rel = SchemaRelation(
                column_name=rel_def.column_name,
                target_package=rel_def.target_package,
                target_table=rel_def.target_table,
                target_column=rel_def.target_column,
                line_number=rel_def.line_number,
                one_one=rel_def.one_one,
                relation_name=rel_def.relation_name
            )
            # Use column name as key if available, otherwise use target table
            key = rel_def.column_name or rel_def.target_table
            schema_table.relations[key] = schema_rel

        return schema_table

    def _build_inverse_relations(self) -> None:
        """Build inverse relations from one_one definitions"""
        for table in self.schema.tables.values():
            for rel_name, rel in table.relations.items():
                if rel.one_one:
                    # Create inverse relation on target table
                    target_fullname = rel.target_fullname
                    if not rel.target_package:
                        target_fullname = f"{table.package}.{rel.target_table}"

                    target_table = self.schema.get_table(target_fullname)
                    if target_table and rel.one_one not in target_table.relations:
                        # Add inverse relation
                        inverse_rel = SchemaRelation(
                            column_name=rel.one_one,
                            target_package=table.package,
                            target_table=table.name,
                            target_column=table.pkey or 'id',
                            line_number=rel.line_number,
                            source_table=table.fullname,
                            is_inverse=True
                        )
                        target_table.relations[rel.one_one] = inverse_rel
