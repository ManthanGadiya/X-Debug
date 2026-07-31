"""C++ language parser backed by tree-sitter."""

from __future__ import annotations

import tree_sitter_cpp as tscpp
from tree_sitter import Language as TreeSitterLanguage
from tree_sitter import Node

from app.analysis.model import ClassDef, FunctionDef
from app.analysis.parsers.treesitter import (
    TreeSitterParser,
    _calls_in_node,
    _function_declarator,
    _node_text,
)
from app.projects.languages import Language


class CPParser(TreeSitterParser):
    """Parse C++ source into the canonical :class:`ModuleAST` model."""

    language = Language.CPP

    @property
    def _ts_language(self) -> TreeSitterLanguage:
        return TreeSitterLanguage(tscpp.language())

    def _class_from_node(self, node: Node, source: str) -> ClassDef | None:
        if node.type != "class_specifier":
            return None
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return None
        name = _node_text(name_node, source)
        return ClassDef(
            name=name,
            qualname=name,
            bases=_bases(node, source),
            methods=_methods(node, source),
            line=node.start_point.row + 1,
        )


def _bases(node: Node, source: str) -> list[str]:
    clause = node.child_by_field_name("base_class_clause")
    if clause is None:
        for child in node.children:
            if child.type == "base_class_clause":
                clause = child
                break
    if clause is None:
        return []
    bases: list[str] = []
    for child in clause.children:
        if child.type in ("type_identifier", "template_type"):
            bases.append(_node_text(child, source))
    return bases


def _methods(node: Node, source: str) -> list[FunctionDef]:
    body = node.child_by_field_name("body")
    if body is None:
        return []
    methods: list[FunctionDef] = []
    for child in body.children:
        if child.type == "function_definition":
            method = _method_from_function_definition(child, source)
            if method is not None:
                methods.append(method)
        elif child.type == "field_declaration":
            method = _method_from_field_declaration(child, source)
            if method is not None:
                methods.append(method)
    return methods


def _method_from_field_declaration(node: Node, source: str) -> FunctionDef | None:
    declarator = node.child_by_field_name("declarator")
    if declarator is None or declarator.type != "function_declarator":
        return None
    signature = _function_declarator(declarator, source)
    if signature is None:
        return None
    name, params = signature
    return FunctionDef(
        name=name,
        qualname=name,
        params=params,
        line=node.start_point.row + 1,
    )


def _method_from_function_definition(node: Node, source: str) -> FunctionDef | None:
    declarator = node.child_by_field_name("declarator")
    if declarator is None:
        return None
    signature = _function_declarator(declarator, source)
    if signature is None:
        return None
    name, params = signature
    return FunctionDef(
        name=name,
        qualname=name,
        params=params,
        line=node.start_point.row + 1,
        calls=_calls_in_node(node, source),
    )
