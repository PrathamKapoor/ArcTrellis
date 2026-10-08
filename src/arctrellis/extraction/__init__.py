"""Canonical semantic entities from normalized source, without graph inference."""

from .errors import (ExtractionError, SemanticExtractionError, SourceDecodingError,
                     UnsupportedExtractionLanguageError)
from .ids import make_entity_id
from .models import ExtractionResult
from .python import extract_python_entities
from .javascript import extract_javascript_entities, extract_typescript_entities
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource


def extract_entities(parsed_source: ParsedSource) -> ExtractionResult:
    """Dispatch one owned source to its explicit canonical-language extractor."""
    if not isinstance(parsed_source, ParsedSource):
        raise TypeError("parsed_source must be ParsedSource")
    extractors = {Language.PYTHON: extract_python_entities,
                  Language.JAVASCRIPT: extract_javascript_entities,
                  Language.TYPESCRIPT: extract_typescript_entities}
    extractor = extractors.get(parsed_source.language)
    if extractor is None:
        raise UnsupportedExtractionLanguageError("no extractor for source language")
    return extractor(parsed_source)

__all__ = ["ExtractionError", "ExtractionResult", "SemanticExtractionError", "SourceDecodingError",
           "UnsupportedExtractionLanguageError", "extract_python_entities", "make_entity_id",
           "extract_javascript_entities", "extract_typescript_entities", "extract_entities"]
