#!/usr/bin/env python
# encoding: utf-8
"""
Model parser for gnrtest

Extracts schema information from Genropy model files using AST.
Works without Genropy runtime.
"""
import ast
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from pathlib import Path


@dataclass
class ColumnDef:
    """Extracted column definition"""
    name: str
    dtype: Optional[str] = None
    size: Optional[str] = None
    line_number: int = 0
    attributes: Dict[str, Any] = field(default_factory=dict)
    # For special column types
    column_type: str = 'column'  # 'column', 'formulaColumn', 'aliasColumn', 'pyColumn'
    formula: Optional[str] = None
    relation_path: Optional[str] = None  # For aliasColumn
    py_method: Optional[str] = None  # For pyColumn


@dataclass
class RelationDef:
    """Extracted relation definition"""
    column_name: str
    target: str  # 'pkg.table.column' or 'table.column'
    line_number: int = 0
    mode: Optional[str] = None  # 'O', 'M', etc.
    one_name: Optional[str] = None
    many_name: Optional[str] = None
    one_one: Optional[str] = None  # Inverse relation name on target table
    relation_name: Optional[str] = None  # Name of this relation
    attributes: Dict[str, Any] = field(default_factory=dict)

    @property
    def target_package(self) -> Optional[str]:
        """Extract package from target"""
        parts = self.target.split('.')
        if len(parts) == 3:
            return parts[0]
        return None

    @property
    def target_table(self) -> str:
        """Extract table from target"""
        parts = self.target.split('.')
        if len(parts) == 3:
            return parts[1]
        elif len(parts) == 2:
            return parts[0]
        return self.target

    @property
    def target_column(self) -> str:
        """Extract column from target"""
        parts = self.target.split('.')
        return parts[-1]


@dataclass
class TableDef:
    """Extracted table definition"""
    name: str
    package: str
    file_path: str
    line_number: int = 0
    pkey: Optional[str] = None
    name_long: Optional[str] = None
    name_plural: Optional[str] = None
    caption_field: Optional[str] = None
    columns: List[ColumnDef] = field(default_factory=list)
    relations: List[RelationDef] = field(default_factory=list)
    methods: Set[str] = field(default_factory=set)
    attributes: Dict[str, Any] = field(default_factory=dict)
    base_class: Optional[str] = None  # Base class if not 'object'

    @property
    def has_specialized_base(self) -> bool:
        """Check if table extends a specialized Genropy base class"""
        if not self.base_class or self.base_class == 'object':
            return False
        # Known Genropy base classes that handle their own config
        specialized_bases = {
            'AttachmentTable', 'GnrDboTable', 'TableBase',
            'RecordHistoryTable', 'ExternalDocTable'
        }
        return self.base_class in specialized_bases


@dataclass
class ParseResult:
    """Result of parsing a model file"""
    file_path: str
    tables: List[TableDef] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class ModelParser:
    """
    Parses Genropy model files using Python AST.

    Extracts:
    - Table definitions (pkg.table())
    - Column definitions (tbl.column(), formulaColumn, aliasColumn, pyColumn)
    - Relation definitions (.relation())
    - Table class methods
    """

    # Regex for formula references
    COLUMN_REF = re.compile(r'\$([a-zA-Z_][a-zA-Z0-9_]*)')
    RELATION_REF = re.compile(r'@([a-zA-Z_][a-zA-Z0-9_.@]*)')

    def __init__(self):
        self._current_package = ''

    def parse_package(self, package_path: str, package_name: str) -> List[TableDef]:
        """
        Parse all model files in a package.

        Args:
            package_path: Path to the package directory
            package_name: Name of the package

        Returns:
            List of TableDef for all tables in the package
        """
        self._current_package = package_name
        tables = []

        model_path = os.path.join(package_path, 'model')
        if not os.path.isdir(model_path):
            return tables

        for fname in os.listdir(model_path):
            if fname.endswith('.py') and not fname.startswith('_'):
                file_path = os.path.join(model_path, fname)
                result = self.parse_file(file_path, package_name)
                tables.extend(result.tables)

        return tables

    def parse_file(self, file_path: str, package_name: str) -> ParseResult:
        """
        Parse a single model file.

        Args:
            file_path: Path to the model Python file
            package_name: Name of the package

        Returns:
            ParseResult with extracted tables
        """
        self._current_package = package_name
        result = ParseResult(file_path=file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=file_path)

            # Extract table definitions
            table_def = self._extract_table(tree, file_path, package_name)
            if table_def:
                result.tables.append(table_def)

        except SyntaxError as e:
            result.errors.append(f"Syntax error: {e}")
        except Exception as e:
            result.errors.append(f"Parse error: {e}")

        return result

    def _extract_table(
        self,
        tree: ast.AST,
        file_path: str,
        package_name: str
    ) -> Optional[TableDef]:
        """Extract table definition from AST"""
        # Find Table class
        table_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'Table':
                table_class = node
                break

        if not table_class:
            return None

        # Get table name from filename
        table_name = os.path.basename(file_path)[:-3]  # Remove .py

        # Extract base class
        base_class = None
        if table_class.bases:
            base = table_class.bases[0]
            if isinstance(base, ast.Name):
                base_class = base.id
            elif isinstance(base, ast.Attribute):
                base_class = base.attr

        table_def = TableDef(
            name=table_name,
            package=package_name,
            file_path=file_path,
            line_number=table_class.lineno if table_class else 0,
            base_class=base_class
        )

        # Extract methods
        for node in table_class.body:
            if isinstance(node, ast.FunctionDef):
                table_def.methods.add(node.name)

        # Find config method and extract table configuration
        for node in table_class.body:
            if isinstance(node, ast.FunctionDef) and node.name == 'config_db':
                self._extract_from_config_db(node, table_def)

        return table_def

    def _extract_from_config_db(self, config_method: ast.FunctionDef, table_def: TableDef) -> None:
        """Extract columns and relations from config_db method"""
        has_sysfields = False

        for node in ast.walk(config_method):
            if not isinstance(node, ast.Call):
                continue

            call_name = self._get_call_name(node)
            if not call_name:
                continue

            # Detect self.sysFields() call
            if call_name == 'self.sysFields' or call_name.endswith('.sysFields'):
                has_sysfields = True

            # pkg.table() call - extract pkey and other attributes
            if '.table' in call_name and call_name.endswith('.table'):
                attrs = self._extract_kwargs(node)
                table_def.pkey = attrs.get('pkey')
                table_def.name_long = attrs.get('name_long')
                table_def.name_plural = attrs.get('name_plural')
                table_def.caption_field = attrs.get('caption_field')
                table_def.attributes = attrs
                if node.args:
                    name = self._get_string(node.args[0])
                    if name:
                        table_def.name = name

            # tbl.column() call
            elif call_name.endswith('.column'):
                col = self._parse_column(node, 'column')
                if col:
                    table_def.columns.append(col)

            # tbl.formulaColumn() call
            elif call_name.endswith('.formulaColumn'):
                col = self._parse_column(node, 'formulaColumn')
                if col:
                    table_def.columns.append(col)

            # tbl.aliasColumn() call
            elif call_name.endswith('.aliasColumn'):
                col = self._parse_alias_column(node)
                if col:
                    table_def.columns.append(col)

            # tbl.pyColumn() call
            elif call_name.endswith('.pyColumn'):
                col = self._parse_pycolumn(node)
                if col:
                    table_def.columns.append(col)

            # .relation() call - can be standalone or chained on column()
            elif call_name.endswith('.relation') or call_name == 'relation':
                rel = self._parse_relation(node)
                if rel:
                    table_def.relations.append(rel)

        # Add system fields if sysFields() was called
        if has_sysfields:
            sys_columns = ['id', '__mod_ts', '__ins_ts', '__version', '__moved']
            for sys_col in sys_columns:
                if not any(c.name == sys_col for c in table_def.columns):
                    table_def.columns.append(ColumnDef(
                        name=sys_col,
                        column_type='system',
                        line_number=0
                    ))

        # Ensure pkey column exists
        if table_def.pkey and not any(c.name == table_def.pkey for c in table_def.columns):
            table_def.columns.append(ColumnDef(
                name=table_def.pkey,
                column_type='pkey',
                line_number=0
            ))

    def _parse_column(self, node: ast.Call, col_type: str) -> Optional[ColumnDef]:
        """Parse a column() or formulaColumn() call"""
        if not node.args:
            return None

        name = self._get_string(node.args[0])
        if not name:
            return None

        attrs = self._extract_kwargs(node)

        formula = None
        if col_type == 'formulaColumn':
            if len(node.args) > 1:
                formula = self._get_string(node.args[1])
            if not formula:
                formula = attrs.get('sql_formula')

        return ColumnDef(
            name=name,
            dtype=attrs.get('dtype'),
            size=str(attrs.get('size', '')) if attrs.get('size') else None,
            line_number=node.lineno,
            attributes=attrs,
            column_type=col_type,
            formula=formula
        )

    def _parse_alias_column(self, node: ast.Call) -> Optional[ColumnDef]:
        """Parse an aliasColumn() call"""
        if len(node.args) < 2:
            return None

        name = self._get_string(node.args[0])
        relation_path = self._get_string(node.args[1])

        if not name:
            return None

        attrs = self._extract_kwargs(node)

        return ColumnDef(
            name=name,
            line_number=node.lineno,
            attributes=attrs,
            column_type='aliasColumn',
            relation_path=relation_path or attrs.get('relation_path')
        )

    def _parse_pycolumn(self, node: ast.Call) -> Optional[ColumnDef]:
        """Parse a pyColumn() call"""
        if not node.args:
            return None

        name = self._get_string(node.args[0])
        if not name:
            return None

        attrs = self._extract_kwargs(node)

        return ColumnDef(
            name=name,
            dtype=attrs.get('dtype'),
            line_number=node.lineno,
            attributes=attrs,
            column_type='pyColumn',
            py_method=attrs.get('py_method', name)
        )

    def _parse_relation(self, node: ast.Call) -> Optional[RelationDef]:
        """Parse a .relation() call"""
        if not node.args:
            return None

        target = self._get_string(node.args[0])
        if not target:
            return None

        attrs = self._extract_kwargs(node)

        # Try to get column name from the chain (tbl.column('x').relation(...))
        column_name = self._get_column_name_from_chain(node)

        return RelationDef(
            column_name=column_name,
            target=target,
            line_number=node.lineno,
            mode=attrs.get('mode'),
            one_name=attrs.get('one_name'),
            many_name=attrs.get('many_name'),
            one_one=attrs.get('one_one'),  # Inverse relation on target table
            relation_name=attrs.get('relation_name'),
            attributes=attrs
        )

    def _get_column_name_from_chain(self, relation_node: ast.Call) -> str:
        """Try to extract column name from call chain"""
        # relation() is called on a column: tbl.column('name').relation(...)
        # We need to go up the chain
        if isinstance(relation_node.func, ast.Attribute):
            value = relation_node.func.value
            if isinstance(value, ast.Call):
                # This is the column() call
                if value.args:
                    return self._get_string(value.args[0]) or ''
        return ''

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """Get full dotted name of a call"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return '.'.join(reversed(parts))
        return None

    def _get_string(self, node: ast.AST) -> Optional[str]:
        """Get string value from node"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.Str):
            return node.s
        return None

    def _extract_kwargs(self, node: ast.Call) -> Dict[str, Any]:
        """Extract keyword arguments"""
        result = {}
        for kw in node.keywords:
            if kw.arg:
                result[kw.arg] = self._get_value(kw.value)
        return result

    def _get_value(self, node: ast.AST) -> Any:
        """Get Python value from AST node"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.NameConstant):
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.List):
            return [self._get_value(e) for e in node.elts]
        elif isinstance(node, ast.Dict):
            return {
                self._get_value(k): self._get_value(v)
                for k, v in zip(node.keys, node.values)
                if k is not None
            }
        return None

    @classmethod
    def extract_formula_refs(cls, formula: str) -> Dict[str, Set[str]]:
        """
        Extract column and relation references from a formula.

        Args:
            formula: SQL formula string

        Returns:
            Dict with 'columns' and 'relations' sets
        """
        columns = set(cls.COLUMN_REF.findall(formula))
        relations = set(cls.RELATION_REF.findall(formula))
        return {'columns': columns, 'relations': relations}
