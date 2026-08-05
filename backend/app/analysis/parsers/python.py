"""Python parser.

Uses the standard library ``ast`` module to extract the canonical model:
imports, functions (with calls and decorators), classes (with bases and
methods), and module-level variable assignments. Because ``ast`` ships with
Python, this parser has zero external dependencies.
"""

from __future__ import annotations

import ast

from app.analysis.model import ClassDef, FunctionDef, ImportRecord, ModuleAST, VariableRecord
from app.analysis.parsers.base import Parser
from app.projects.languages import Language


class PythonParser(Parser):
    """Parse Python source into the canonical AST model."""

    language = Language.PYTHON
    thread_safe = True

    def parse(self, source: str, path: str) -> ModuleAST:
        """Parse ``source`` and return its canonical representation."""
        tree = ast.parse(source, filename=path)
        module = ModuleAST(path=path, language=self.language)
        module.imports = _extract_imports(tree)
        module.variables = _extract_variables(tree)
        module.functions = _extract_functions(tree, prefix="")
        module.classes = _extract_classes(tree)
        return module


def _extract_imports(tree: ast.AST) -> list[ImportRecord]:
    imports: list[ImportRecord] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    ImportRecord(
                        module=alias.name,
                        names=[alias.asname or alias.name.split(".")[0]],
                        line=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            imports.append(
                ImportRecord(
                    module=node.module or "",
                    names=[alias.asname or alias.name for alias in node.names],
                    line=node.lineno,
                )
            )
    return imports


def _extract_variables(tree: ast.AST) -> list[VariableRecord]:
    variables: list[VariableRecord] = []
    for node in tree.body:  # type: ignore[attr-defined]
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                variables.extend(_target_names(target, scope="module", line=node.lineno))
    return variables


def _target_names(node: ast.AST, *, scope: str, line: int) -> list[VariableRecord]:
    if isinstance(node, ast.Name):
        return [VariableRecord(name=node.id, line=line, scope=scope)]
    if isinstance(node, (ast.Tuple, ast.List)):
        records: list[VariableRecord] = []
        for element in node.elts:
            records.extend(_target_names(element, scope=scope, line=line))
        return records
    if isinstance(node, ast.Attribute):
        return _target_names(node.value, scope=scope, line=line)
    return []


def _extract_functions(tree: ast.AST, *, prefix: str) -> list[FunctionDef]:
    functions: list[FunctionDef] = []
    for node in tree.body:  # type: ignore[attr-defined]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualname = f"{prefix}{node.name}"
            functions.append(
                FunctionDef(
                    name=node.name,
                    qualname=qualname,
                    params=[arg.arg for arg in node.args.args],
                    line=node.lineno,
                    calls=_extract_calls(node),
                    decorators=[_decorator_name(decorator) for decorator in node.decorator_list],
                )
            )
    return functions


def _extract_classes(tree: ast.AST) -> list[ClassDef]:
    classes: list[ClassDef] = []
    for node in tree.body:  # type: ignore[attr-defined]
        if isinstance(node, ast.ClassDef):
            classes.append(
                ClassDef(
                    name=node.name,
                    qualname=node.name,
                    bases=[_expr_name(base) for base in node.bases],
                    methods=[
                        method
                        for statement in node.body
                        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
                        for method in _method_defs(statement, class_name=node.name)
                    ],
                    line=node.lineno,
                )
            )
    return classes


def _method_defs(
    node: ast.FunctionDef | ast.AsyncFunctionDef, *, class_name: str
) -> list[FunctionDef]:
    qualname = f"{class_name}.{node.name}"
    return [
        FunctionDef(
            name=node.name,
            qualname=qualname,
            params=[arg.arg for arg in node.args.args],
            line=node.lineno,
            calls=_extract_calls(node),
            decorators=[_decorator_name(decorator) for decorator in node.decorator_list],
        )
    ]


def _extract_calls(node: ast.AST) -> list[str]:
    calls: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            calls.append(_expr_name(child.func))
    return calls


def _expr_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_expr_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _expr_name(node.func)
    if isinstance(node, ast.Subscript):
        return _expr_name(node.value)
    return ""


def _decorator_name(node: ast.AST) -> str:
    return _expr_name(node)
