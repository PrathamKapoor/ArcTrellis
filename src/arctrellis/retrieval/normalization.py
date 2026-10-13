"""Deterministic Unicode normalization and identifier tokenization for retrieval only.

Policy (D-128):

- Canonical text is NFKC, so visually equivalent spellings share tokens.
- Splitting runs on the *canonical, still cased* text, because case folding first
  would erase the camel/Pascal boundaries that carry retrieval signal. Tokens are
  case folded individually after splitting.
- Separators are every character that is neither a Unicode letter nor a Unicode
  digit, so ``.``/``/``/``\\``/``-``/``_``/whitespace/control characters all split
  without any special-casing and without touching the filesystem.
- ASCII boundaries: acronym runs keep their capitals (``HTTPServer`` ->
  ``http`` + ``server``), Capitalized words, lowercase runs and digit runs are
  separate tokens. Non-ASCII letter runs are kept whole, so a non-ASCII letter
  adjacent to an ASCII run forms its own token.
- Queries are data. Nothing here interprets, resolves, decodes or opens anything.

Original identifiers are never mutated; only derived tokens are affected.
"""

from re import UNICODE
from re import compile as re_compile
from unicodedata import normalize as unicode_normalize

MAX_FIELD_VALUE_LENGTH = 512
MAX_FIELD_TOKENS = 32

_TOKEN_RUN = re_compile(
    r"[A-Z]+(?![a-z])"
    r"|[A-Z][a-z]*"
    r"|[a-z]+"
    r"|[0-9]+"
    r"|[^\W\d_]+",
    UNICODE,
)


def canonical_text(value: str) -> str:
    """NFKC-normalize text while preserving case and every original character."""
    if not isinstance(value, str):
        raise TypeError("retrieval text must be a string")
    return unicode_normalize("NFKC", value)


def fold(value: str) -> str:
    """Case-fold canonical text for exact comparison against original spellings."""
    return canonical_text(value).casefold()


def normalize_exact(value: str) -> str:
    """Whitespace-collapsed case-folded form used for exact field matching."""
    return " ".join(fold(value).split())


def tokenize(value: str, *, max_tokens: int = MAX_FIELD_TOKENS) -> tuple[str, ...]:
    """Split canonical text into case-folded retrieval tokens, preserving order.

    Only the first ``MAX_FIELD_VALUE_LENGTH`` characters of a value are examined
    and at most ``max_tokens`` tokens are produced, so an adversarially long
    identifier or metadata value cannot cause unbounded per-field work.
    """
    if not isinstance(value, str):
        raise TypeError("retrieval text must be a string")
    if type(max_tokens) is not int or max_tokens < 0:
        raise ValueError("max_tokens must be a nonnegative integer")
    text = canonical_text(value)[:MAX_FIELD_VALUE_LENGTH]
    tokens: list[str] = []
    for match in _TOKEN_RUN.finditer(text):
        if len(tokens) == max_tokens:
            break
        tokens.append(match.group().casefold())
    return tuple(tokens)


def tokenize_value(value: str) -> tuple[str, ...]:
    """Tokens for a bounded approved field value."""
    return tokenize(value, max_tokens=MAX_FIELD_TOKENS)
