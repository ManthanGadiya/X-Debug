"""Tree-sitter based parsing for C-family languages.

C and C++ share a grammar shape: preprocessor directives, declarations,
``function_definition`` nodes, and ``call_expression`` nodes. This module
provides the shared traversal machinery; the C and C++ parsers differ only in
which constructs they recognize as classes, methods, and imports.
"""

from __future__ import annotations

from abc import abstractmethod

from tree_sitter import Language as TreeSitterLanguage
from tree_sitter import Node, Parser

from app.analysis.model import ClassDef, FunctionDef, ImportRecord, ModuleAST, VariableRecord
from app.analysis.parsers.base import Parser as BaseParser


class TreeSitterParser(BaseParser):
    """Base parser that delegates syntax analysis to tree-sitter."""

    @property
    @abstractmethod
    def _ts_language(self) -> TreeSitterLanguage:
        """Return the tree-sitter language object for this parser."""

    def __init__(self) -> None:
        self._parser = Parser(self._ts_language)

    def parse(self, source: str, path: str) -> ModuleAST:
        """Parse ``source`` and return its canonical representation."""
        tree = self._parser.parse(source.encode("utf-8"))
        root = tree.root_node
        return ModuleAST(
            path=path,
            language=self.language,
            imports=self._extract_imports(root, source),
            functions=self._extract_functions(root, source),
            classes=self._extract_classes(root, source),
            variables=self._extract_variables(root, source),
        )

    # -- common extraction -------------------------------------------------

    def _extract_imports(self, root: Node, source: str) -> list[ImportRecord]:
        imports: list[ImportRecord] = []
        for node in _walk(root):
            if node.type != "preproc_include":
                continue
            path_node = node.child_by_field_name("path")
            if path_node is None:
                continue
            imports.append(
                ImportRecord(
                    module=_include_name(path_node, source),
                    names=[],
                    line=_line(node),
                )
            )
        return imports

    def _extract_functions(self, root: Node, source: str) -> list[FunctionDef]:
        functions: list[FunctionDef] = []
        for node in _walk(root):
            if node.type != "function_definition":
                continue
            if _inside_class_body(node):
                continue
            function = _function_from_node(node, source)
            if function is not None:
                functions.append(function)
        return functions

    def _extract_classes(self, root: Node, source: str) -> list[ClassDef]:
        classes: list[ClassDef] = []
        for node in _walk(root):
            if node.type not in self._class_node_types:
                continue
            cls = self._class_from_node(node, source)
            if cls is not None:
                classes.append(cls)
        return classes

    @property
    def _class_node_types(self) -> tuple[str, ...]:
        """Node types that represent a class or struct definition."""
        return ("class_specifier", "struct_specifier")

    @abstractmethod
    def _class_from_node(self, node: Node, source: str) -> ClassDef | None:
        """Extract a class definition from a class-like node."""

    def _extract_variables(self, root: Node, source: str) -> list[VariableRecord]:
        variables: list[VariableRecord] = []
        for node in _walk(root):
            if node.type != "declaration":
                continue
            if _inside_function(node) or _is_function_declaration(node):
                continue
            for declarator in _declarators(node):
                name = _node_text(declarator, source)
                if _is_identifier(name):
                    variables.append(VariableRecord(name=name, line=_line(node), scope="module"))
        return variables


def _walk(node: Node) -> list[Node]:
    """Return all descendants of ``node`` in depth-first order, including itself."""
    nodes: list[Node] = []
    stack = [node]
    while stack:
        current = stack.pop()
        nodes.append(current)
        stack.extend(reversed(current.children))
    return nodes


def _node_text(node: Node, source: str) -> str:
    return source[node.start_byte : node.end_byte]


def _line(node: Node) -> int:
    return node.start_point.row + 1


def _include_name(path_node: Node, source: str) -> str:
    text = _node_text(path_node, source)
    if len(text) >= 2 and text[0] in '<"' and text[-1] in '>"':
        return text[1:-1]
    return text


def _is_identifier(text: str) -> bool:
    return text.isidentifier()


def _declarators(node: Node) -> list[Node]:
    """Return the identifier nodes naming a declaration's declarator(s)."""
    declarator = node.child_by_field_name("declarator")
    if declarator is None:
        return []
    return _collect_identifiers(declarator)


def _collect_identifiers(node: Node) -> list[Node]:
    """Descend declarator wrappers and return the naming identifier nodes."""
    if node.type in ("identifier", "field_identifier", "type_identifier"):
        return [node]
    results: list[Node] = []
    for field in ("declarator", "name"):
        child = node.child_by_field_name(field)
        if child is not None:
            results.extend(_collect_identifiers(child))
    return results


def _inside_class_body(node: Node) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type == "field_declaration_list":
            return True
        parent = parent.parent
    return False


def _inside_function(node: Node) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type == "function_definition":
            return True
        parent = parent.parent
    return False


def _is_function_declaration(node: Node) -> bool:
    """Return True when a declaration only declares a function (prototype)."""
    return any(child.type == "function_declarator" for child in node.children)


def _function_from_node(node: Node, source: str) -> FunctionDef | None:
    declarator = node.child_by_field_name("declarator")
    if declarator is None:
        return None
    function = _function_declarator(declarator, source)
    if function is None:
        return None
    name, params = function
    calls = _calls_in_node(node, source)
    return FunctionDef(
        name=name,
        qualname=name,
        params=params,
        line=_line(node),
        calls=calls,
    )


def _function_declarator(node: Node, source: str) -> tuple[str, list[str]] | None:
    """Return ``(name, params)`` from a ``function_declarator`` node."""
    if node.type != "function_declarator":
        return None
    name_node = node.child_by_field_name("declarator")
    if name_node is None:
        return None
    name = _node_text(name_node, source)
    if not _is_identifier(name):
        name = _qualified_name_tail(name)
    params = _parameters(node, source)
    return name, params


def _qualified_name_tail(text: str) -> str:
    """Return the last segment of a qualified name such as ``Greeter::greet``."""
    return text.rsplit("::", 1)[-1]


def _parameters(node: Node, source: str) -> list[str]:
    params_node = node.child_by_field_name("parameters")
    if params_node is None:
        return []
    params: list[str] = []
    for child in params_node.children:
        if child.type != "parameter_declaration":
            continue
        declarator = child.child_by_field_name("declarator")
        if declarator is not None:
            params.append(_node_text(declarator, source))
    return params


def _calls_in_node(node: Node, source: str) -> list[str]:
    calls: list[str] = []
    for child in _walk(node):
        if child.type != "call_expression":
            continue
        function = child.child_by_field_name("function")
        if function is None:
            continue
        name = _call_name(function, source)
        if name:
            calls.append(name)
    return calls


def _call_name(function: Node, source: str) -> str:
    if function.type in ("identifier", "field_identifier"):
        return _node_text(function, source)
    if function.type == "field_expression":
        field = function.child_by_field_name("field")
        return _node_text(field, source) if field is not None else ""
    if function.type == "qualified_identifier":
        name = function.child_by_field_name("name")
        return _node_text(name, source) if name is not None else ""
    return ""
