"""Private grammar selection; no mutable parser instance is shared."""

from __future__ import annotations

from importlib import import_module
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from arctrellis.ingestion import DiscoveredFile, Language

from .errors import ParserConfigurationError, UnsupportedLanguageError

if TYPE_CHECKING:
    from tree_sitter import Parser

_GRAMMARS = {
    ".py": (Language.PYTHON, "python"),
    ".pyi": (Language.PYTHON, "python"),
    ".js": (Language.JAVASCRIPT, "javascript"),
    ".jsx": (Language.JAVASCRIPT, "javascript"),
    ".mjs": (Language.JAVASCRIPT, "javascript"),
    ".cjs": (Language.JAVASCRIPT, "javascript"),
    ".ts": (Language.TYPESCRIPT, "typescript"),
    ".mts": (Language.TYPESCRIPT, "typescript"),
    ".cts": (Language.TYPESCRIPT, "typescript"),
    ".tsx": (Language.TYPESCRIPT, "tsx"),
}


def _grammar_for(path: str, language: Language | None) -> str:
    DiscoveredFile(path, 0, language)
    selected = _GRAMMARS.get(PurePosixPath(path).suffix.lower())
    if selected is None or language is None or selected[0] != language:
        raise UnsupportedLanguageError(f"no compatible grammar for {path!r} with language {language!r}")
    return selected[1]


def _new_parser(grammar: str) -> Parser:
    try:
        from tree_sitter import Language as ParserLanguage
        from tree_sitter import Parser

        if grammar in ("typescript", "tsx"):
            module = import_module("tree_sitter_typescript")
            capsule = module.language_tsx() if grammar == "tsx" else module.language_typescript()
        else:
            module = import_module(f"tree_sitter_{grammar}")
            capsule = module.language()
        return Parser(ParserLanguage(capsule))
    except (ImportError, AttributeError, TypeError, ValueError, RuntimeError) as error:
        raise ParserConfigurationError(f"cannot initialize {grammar} grammar") from error
