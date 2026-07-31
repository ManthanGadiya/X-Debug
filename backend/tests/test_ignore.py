"""Unit tests for ignore rules."""

from __future__ import annotations

from app.projects.ignore import _BINARY_EXTENSIONS, _IGNORED_DIRECTORIES, IgnoreRules


def test_ignores_binary_extensions() -> None:
    """Binary extensions are always excluded."""
    rules = IgnoreRules()
    assert rules.is_ignored("lib/foo.so")
    assert rules.is_ignored("assets/logo.png")
    assert rules.is_ignored("data/archive.zip")
    assert rules.is_ignored("app/__pycache__/x.cpython-312.pyc")


def test_ignores_ignored_directories() -> None:
    """Known dependency and build directories are always excluded."""
    rules = IgnoreRules()
    assert rules.is_ignored("node_modules/pkg/index.js")
    assert rules.is_ignored("dist/bundle.js")
    assert rules.is_ignored("build/main.o")
    assert rules.is_ignored(".venv/lib/python.py")


def test_ignores_known_files() -> None:
    """OS-specific files are excluded."""
    rules = IgnoreRules()
    assert rules.is_ignored(".DS_Store")
    assert rules.is_ignored("Thumbs.db")


def test_does_not_ignore_source_files() -> None:
    """Source and documentation files pass the rules."""
    rules = IgnoreRules()
    assert not rules.is_ignored("src/main.py")
    assert not rules.is_ignored("lib/header.h")
    assert not rules.is_ignored("README.md")


def test_gitignore_patterns_are_respected() -> None:
    """Explicit gitignore-style patterns are honored."""
    rules = IgnoreRules.from_lines(["*.generated.py", "vendor/", "!vendor/keep.py"])
    assert rules.is_ignored("gen.generated.py")
    assert rules.is_ignored("vendor/pkg.js")
    assert not rules.is_ignored("vendor/keep.py")


def test_empty_rules_ignore_nothing() -> None:
    """A rule set without patterns excludes nothing by default."""
    rules = IgnoreRules()
    assert not rules.is_ignored("src/lib/util.py")


def test_windows_style_paths_are_normalized() -> None:
    """Windows path separators normalize to the same rules."""
    rules = IgnoreRules()
    assert rules.is_ignored("node_modules\\pkg\\index.js")


def test_binary_extension_table_is_nonempty() -> None:
    """The extension and directory tables contain the default sets."""
    assert _BINARY_EXTENSIONS
    assert _IGNORED_DIRECTORIES


def test_from_root_loads_gitignore_files(tmp_path) -> None:
    """Nested .gitignore files are collected and applied from the root."""
    (tmp_path / ".gitignore").write_text("# comment\n*.generated.py\nbuild/\n", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / ".gitignore").write_text("secret.txt\n", encoding="utf-8")

    rules = IgnoreRules.from_root(tmp_path)

    assert rules.is_ignored("gen.generated.py")
    assert rules.is_ignored("build/app.js")
    assert rules.is_ignored("nested/secret.txt")
    assert not rules.is_ignored("nested/main.py")
    assert not rules.is_ignored("main.py")
