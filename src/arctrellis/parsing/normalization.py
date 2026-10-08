"""The only conversion from native syntax nodes to ArcTrellis values."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

from .models import DiagnosticKind, ParseDiagnostic, SyntaxNode, SyntaxSpan


def _span(node: Node) -> SyntaxSpan:
    return SyntaxSpan(
        node.start_byte,
        node.end_byte,
        node.start_point.row + 1,
        node.start_point.column,
        node.end_point.row + 1,
        node.end_point.column,
    )


def _capture(node: Node, field: str | None) -> SyntaxNode:
    return SyntaxNode(node.type, _span(node), field, (), node.is_error, node.is_missing, node.is_named)


def _normalize_tree(root: Node) -> tuple[SyntaxNode, tuple[ParseDiagnostic, ...]]:
    def children(node: Node) -> Iterator[tuple[Node, str | None]]:
        for index, child in enumerate(node.children):
            yield child, node.field_name_for_child(index)

    # Native child objects avoid cursor-backed point access on the Windows binding.
    frames: list[tuple[SyntaxNode, Iterator[tuple[Node, str | None]], list[SyntaxNode]]] = [
        (_capture(root, None), children(root), [])
    ]
    while frames:
        captured, remaining, completed = frames[-1]
        try:
            child, field = next(remaining)
        except StopIteration:
            frames.pop()
            retained = captured.is_named or captured.is_error or captured.is_missing or not frames
            if retained:
                normalized = SyntaxNode(
                    captured.kind,
                    captured.span,
                    captured.field_name,
                    tuple(completed),
                    captured.is_error,
                    captured.is_missing,
                    captured.is_named,
                )
                if frames:
                    frames[-1][2].append(normalized)
            elif frames:
                # Rare unnamed wrappers must not hide named or recovery descendants.
                frames[-1][2].extend(completed)
            if not frames:
                diagnostics = []
                for node in normalized.walk():
                    if node.is_error:
                        diagnostics.append(ParseDiagnostic(DiagnosticKind.ERROR, node.kind, node.span))
                    if node.is_missing:
                        diagnostics.append(ParseDiagnostic(DiagnosticKind.MISSING, node.kind, node.span))
                return normalized, tuple(diagnostics)
        else:
            frames.append((_capture(child, field), children(child), []))
    raise RuntimeError("native tree normalization did not produce a root")
