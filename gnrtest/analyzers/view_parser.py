#!/usr/bin/env python
# encoding: utf-8
"""
View parser for gnrtest

Extracts information from Genropy view files (th_*.py) using AST.
"""
import ast
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set


@dataclass
class FieldcellDef:
    """Extracted fieldcell definition"""
    field: str
    line_number: int
    is_relation_path: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FieldDef:
    """Extracted field definition (in forms)"""
    field: str
    line_number: int
    is_relation_path: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableHandlerDef:
    """Extracted tablehandler definition"""
    handler_type: str  # 'dialogTableHandler', 'inlineTableHandler'
    line_number: int
    relation: Optional[str] = None
    relation_has_at: bool = True
    view_resource: Optional[str] = None
    form_resource: Optional[str] = None
    condition: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceDef:
    """Extracted resource class definition"""
    name: str
    class_type: str  # 'View', 'Form', etc.
    line_number: int
    methods: Set[str] = field(default_factory=set)


@dataclass
class ViewFileDef:
    """Complete parsed view file"""
    file_path: str
    table_name: str
    resources: List[ResourceDef] = field(default_factory=list)
    fieldcells: List[FieldcellDef] = field(default_factory=list)
    fields: List[FieldDef] = field(default_factory=list)
    table_handlers: List[TableHandlerDef] = field(default_factory=list)
    has_view_class: bool = False
    has_form_class: bool = False
    th_struct_line: Optional[int] = None
    th_struct_has_fieldcells: bool = False
    errors: List[str] = field(default_factory=list)


class ViewParser:
    """
    Parses Genropy view files (th_*.py) using AST.

    Extracts:
    - Resource classes (View, Form)
    - fieldcell() calls
    - field() calls
    - dialogTableHandler/inlineTableHandler calls
    """

    def parse_package_views(self, package_path: str, package_name: str) -> List[ViewFileDef]:
        """
        Parse all view files in a package.

        Args:
            package_path: Path to the package directory
            package_name: Name of the package

        Returns:
            List of ViewFileDef for all th_*.py files
        """
        views = []
        resources_path = os.path.join(package_path, 'resources', 'tables')

        if not os.path.isdir(resources_path):
            return views

        for root, dirs, files in os.walk(resources_path):
            for fname in files:
                if fname.startswith('th_') and fname.endswith('.py'):
                    file_path = os.path.join(root, fname)
                    view_def = self.parse_file(file_path)
                    views.append(view_def)

        return views

    def parse_file(self, file_path: str) -> ViewFileDef:
        """
        Parse a single view file.

        Args:
            file_path: Path to the th_*.py file

        Returns:
            ViewFileDef with extracted information
        """
        # Extract table name from filename
        filename = os.path.basename(file_path)
        table_name = filename[3:-3] if filename.startswith('th_') else ''

        result = ViewFileDef(file_path=file_path, table_name=table_name)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=file_path)

            # Extract classes
            self._extract_classes(tree, result)

            # Extract calls
            self._extract_calls(tree, result)

        except SyntaxError as e:
            result.errors.append(f"Syntax error: {e}")
        except Exception as e:
            result.errors.append(f"Parse error: {e}")

        return result

    def _extract_classes(self, tree: ast.AST, result: ViewFileDef) -> None:
        """Extract resource class definitions"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Get base classes
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(self._get_attr_name(base))

                # Determine class type
                class_type = node.name
                for base in bases:
                    if 'View' in base or 'Form' in base:
                        class_type = base
                        break

                # Get methods
                methods = {
                    n.name for n in node.body
                    if isinstance(n, ast.FunctionDef)
                }

                resource = ResourceDef(
                    name=node.name,
                    class_type=class_type,
                    line_number=node.lineno,
                    methods=methods
                )
                result.resources.append(resource)

                if node.name == 'View' or 'View' in class_type:
                    result.has_view_class = True
                if node.name == 'Form' or 'Form' in class_type:
                    result.has_form_class = True

                # Check for th_struct
                if 'th_struct' in methods:
                    for method_node in node.body:
                        if isinstance(method_node, ast.FunctionDef) and method_node.name == 'th_struct':
                            result.th_struct_line = method_node.lineno
                            # Count fieldcells in th_struct
                            for inner in ast.walk(method_node):
                                if isinstance(inner, ast.Call):
                                    call_name = self._get_call_name(inner)
                                    if call_name and call_name.endswith('.fieldcell'):
                                        result.th_struct_has_fieldcells = True
                                        break

    def _extract_calls(self, tree: ast.AST, result: ViewFileDef) -> None:
        """Extract fieldcell, field, and tablehandler calls"""
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            call_name = self._get_call_name(node)
            if not call_name:
                continue

            # fieldcell calls
            if call_name.endswith('.fieldcell'):
                fc = self._parse_fieldcell(node)
                if fc:
                    result.fieldcells.append(fc)

            # field calls
            elif call_name.endswith('.field'):
                fld = self._parse_field(node)
                if fld:
                    result.fields.append(fld)

            # tablehandler calls
            elif call_name.endswith('.dialogTableHandler'):
                th = self._parse_tablehandler(node, 'dialogTableHandler')
                if th:
                    result.table_handlers.append(th)

            elif call_name.endswith('.inlineTableHandler'):
                th = self._parse_tablehandler(node, 'inlineTableHandler')
                if th:
                    result.table_handlers.append(th)

    def _parse_fieldcell(self, node: ast.Call) -> Optional[FieldcellDef]:
        """Parse a fieldcell() call"""
        if not node.args:
            return None

        field_val = self._get_string(node.args[0])
        if not field_val:
            return None

        return FieldcellDef(
            field=field_val,
            line_number=node.lineno,
            is_relation_path=field_val.startswith('@'),
            attributes=self._extract_kwargs(node)
        )

    def _parse_field(self, node: ast.Call) -> Optional[FieldDef]:
        """Parse a field() call"""
        if not node.args:
            return None

        field_val = self._get_string(node.args[0])
        if not field_val:
            return None

        return FieldDef(
            field=field_val,
            line_number=node.lineno,
            is_relation_path=field_val.startswith('@'),
            attributes=self._extract_kwargs(node)
        )

    def _parse_tablehandler(self, node: ast.Call, handler_type: str) -> TableHandlerDef:
        """Parse a tablehandler call"""
        attrs = self._extract_kwargs(node)
        relation = attrs.get('relation')

        return TableHandlerDef(
            handler_type=handler_type,
            line_number=node.lineno,
            relation=relation,
            relation_has_at=relation.startswith('@') if relation else True,
            view_resource=attrs.get('viewResource'),
            form_resource=attrs.get('formResource'),
            condition=attrs.get('condition'),
            attributes=attrs
        )

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """Get full dotted name of a call"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return self._get_attr_name(node.func)
        return None

    def _get_attr_name(self, node: ast.Attribute) -> str:
        """Get full dotted attribute name"""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return '.'.join(reversed(parts))

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
        elif isinstance(node, ast.Name):
            return node.id
        return None
