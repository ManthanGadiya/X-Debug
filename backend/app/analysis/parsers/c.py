"""C language parser backed by tree-sitter."""

from __future__ import annotations

import tree_sitter_c as tsc
from tree_sitter import Language as TreeSitterLanguage
from tree_sitter import Node

from app.analysis.model import ClassDef
from app.analysis.parsers.treesitter import TreeSitterParser
from app.projects.languages import Language


class CParser(TreeSitterParser):
    """Parse C source into the canonical :class:`ModuleAST` model."""

    language = Language.C

    @property
    def _ts_language(self) -> TreeSitterLanguage:
        return TreeSitterLanguage(tsc.language())

    def _class_from_node(self, node: Node, source: str) -> ClassDef | None:
        if node.type == "class_specifier":
            return None
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return None
        name = _text(name_node, source)
        return ClassDef(
            name=name,
            qualname=name,
            bases=[],
            line=node.start_point.row + 1,
        )


def _text(node: Node, source: str) -> str:
    return source[node.start_byte : node.end_byte]
