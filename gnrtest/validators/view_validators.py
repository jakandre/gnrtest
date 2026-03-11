#!/usr/bin/env python
# encoding: utf-8
"""
View validators for gnrtest

Validates Genropy view definitions (VIEW_001-012).
"""
import os
from typing import List, Dict, Set
from .base import BaseValidator, ValidationError
from ..core.error_catalog import ErrorCatalog
from ..core.schema_builder import Schema
from ..analyzers.view_parser import ViewParser, ViewFileDef


class FieldcellColumnValidator(BaseValidator):
    """Validates fieldcell column references (VIEW_001)"""

    def __init__(self, schema: Schema, views: List[ViewFileDef]):
        super().__init__(schema)
        self.views = views

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for view in self.views:
            table_fullname = f"{package}.{view.table_name}"

            # Check if table exists
            if not self.schema.get_table(table_fullname):
                continue  # Handled by VIEW_004

            for fc in view.fieldcells:
                if fc.is_relation_path:
                    continue  # Handled by VIEW_002

                if not self.schema.column_exists(table_fullname, fc.field):
                    self.add_error(
                        ErrorCatalog.VIEW_001,
                        view.file_path,
                        fc.line_number,
                        package=package,
                        table=view.table_name,
                        field=fc.field
                    )

        return self.get_errors()


class FieldcellRelationValidator(BaseValidator):
    """Validates fieldcell relation paths (VIEW_002, VIEW_006)"""

    def __init__(self, schema: Schema, views: List[ViewFileDef]):
        super().__init__(schema)
        self.views = views

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for view in self.views:
            table_fullname = f"{package}.{view.table_name}"

            if not self.schema.get_table(table_fullname):
                continue

            for fc in view.fieldcells:
                if not fc.is_relation_path:
                    continue

                resolved = self.schema.resolve_relation_path(table_fullname, fc.field)
                if not resolved.valid:
                    # Deep path or simple?
                    if fc.field.count('@') > 1:
                        error_code = ErrorCatalog.VIEW_006
                    else:
                        error_code = ErrorCatalog.VIEW_002

                    self.add_error(
                        error_code,
                        view.file_path,
                        fc.line_number,
                        package=package,
                        table=view.table_name,
                        field=fc.field,
                        path=fc.field,
                        error=resolved.error
                    )

        return self.get_errors()


class FormFieldValidator(BaseValidator):
    """Validates form field references (VIEW_003)"""

    def __init__(self, schema: Schema, views: List[ViewFileDef]):
        super().__init__(schema)
        self.views = views

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for view in self.views:
            table_fullname = f"{package}.{view.table_name}"

            if not self.schema.get_table(table_fullname):
                continue

            for fld in view.fields:
                if fld.is_relation_path:
                    resolved = self.schema.resolve_relation_path(table_fullname, fld.field)
                    if not resolved.valid:
                        self.add_error(
                            ErrorCatalog.VIEW_003,
                            view.file_path,
                            fld.line_number,
                            package=package,
                            table=view.table_name,
                            field=fld.field
                        )
                else:
                    if not self.schema.column_exists(table_fullname, fld.field):
                        self.add_error(
                            ErrorCatalog.VIEW_003,
                            view.file_path,
                            fld.line_number,
                            package=package,
                            table=view.table_name,
                            field=fld.field
                        )

        return self.get_errors()


class ViewTableExistsValidator(BaseValidator):
    """Validates view has corresponding table (VIEW_004)"""

    def __init__(self, schema: Schema, views: List[ViewFileDef]):
        super().__init__(schema)
        self.views = views

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for view in self.views:
            table_fullname = f"{package}.{view.table_name}"

            if not self.schema.get_table(table_fullname):
                self.add_error(
                    ErrorCatalog.VIEW_004,
                    view.file_path,
                    1,
                    package=package,
                    resource=os.path.basename(view.file_path),
                    table=view.table_name
                )

        return self.get_errors()


class CaptionFieldValidator(BaseValidator):
    """Validates caption_field exists (VIEW_005)"""

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for table_name in self.schema.get_package_tables(package):
            table = self.schema.get_table(f"{package}.{table_name}")
            if not table or not table.caption_field:
                continue

            if not self.schema.column_exists(table.fullname, table.caption_field):
                self.add_error(
                    ErrorCatalog.VIEW_005,
                    table.file_path,
                    table.line_number,
                    package=package,
                    table=table_name,
                    caption_field=table.caption_field
                )

        return self.get_errors()


class TableHandlerRelationValidator(BaseValidator):
    """Validates tablehandler relation syntax (VIEW_007)"""

    def __init__(self, schema: Schema, views: List[ViewFileDef]):
        super().__init__(schema)
        self.views = views

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for view in self.views:
            for th in view.table_handlers:
                if th.relation and not th.relation_has_at:
                    self.add_error(
                        ErrorCatalog.VIEW_007,
                        view.file_path,
                        th.line_number,
                        package=package,
                        relation=th.relation,
                        suggestion=f"@{th.relation}"
                    )

        return self.get_errors()


class ResourceExistsValidator(BaseValidator):
    """Validates viewResource/formResource exist (VIEW_008)"""

    def __init__(self, schema: Schema, views: List[ViewFileDef]):
        super().__init__(schema)
        self.views = views

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        # Build map of available resources
        resources_map: Dict[str, Set[str]] = {}
        for view in self.views:
            if view.table_name not in resources_map:
                resources_map[view.table_name] = set()
            for res in view.resources:
                resources_map[view.table_name].add(res.name)

        for view in self.views:
            for th in view.table_handlers:
                # We'd need to resolve the relation to get target table
                # For now, just check if resource names look reasonable
                if th.view_resource and th.view_resource not in ('View', 'ViewBase'):
                    # Check if it exists anywhere
                    found = False
                    for table_resources in resources_map.values():
                        if th.view_resource in table_resources:
                            found = True
                            break
                    if not found:
                        self.add_error(
                            ErrorCatalog.VIEW_008,
                            view.file_path,
                            th.line_number,
                            package=package,
                            resource_type='viewResource',
                            resource=th.view_resource,
                            table=view.table_name
                        )

        return self.get_errors()


class ViewClassValidator(BaseValidator):
    """Validates View/Form class exists (VIEW_011)"""

    def __init__(self, schema: Schema, views: List[ViewFileDef]):
        super().__init__(schema)
        self.views = views

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for view in self.views:
            if not view.has_view_class and not view.has_form_class:
                if not view.resources:
                    self.add_error(
                        ErrorCatalog.VIEW_011,
                        view.file_path,
                        1,
                        package=package,
                        resource=os.path.basename(view.file_path)
                    )

        return self.get_errors()


class ThStructValidator(BaseValidator):
    """Validates th_struct has fieldcells (VIEW_012)"""

    def __init__(self, schema: Schema, views: List[ViewFileDef]):
        super().__init__(schema)
        self.views = views

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        self.clear_errors()

        for view in self.views:
            if view.th_struct_line and not view.th_struct_has_fieldcells:
                self.add_error(
                    ErrorCatalog.VIEW_012,
                    view.file_path,
                    view.th_struct_line,
                    package=package,
                    resource=os.path.basename(view.file_path)
                )

        return self.get_errors()


class AllViewValidators:
    """Runs all view validators"""

    def __init__(self, schema: Schema, views: List[ViewFileDef]):
        self.schema = schema
        self.views = views
        self.validators = [
            FieldcellColumnValidator(schema, views),
            FieldcellRelationValidator(schema, views),
            FormFieldValidator(schema, views),
            ViewTableExistsValidator(schema, views),
            CaptionFieldValidator(schema),
            TableHandlerRelationValidator(schema, views),
            ResourceExistsValidator(schema, views),
            ViewClassValidator(schema, views),
            ThStructValidator(schema, views),
        ]

    def validate(self, package: str, **kwargs) -> List[ValidationError]:
        """Run all validators"""
        errors = []
        for validator in self.validators:
            errors.extend(validator.validate(package, **kwargs))
        return errors
