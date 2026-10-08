"""Versioned structural/proof identity; repository namespace remains deferred."""

import json
from uuid import NAMESPACE_URL, uuid5

from arctrellis.ingestion import DiscoveredFile, Language


def _stable_id(marker: str, *components: object) -> str:
    return str(uuid5(NAMESPACE_URL, json.dumps([marker, *components], ensure_ascii=True, separators=(",", ":"))))


def _file_id(path: str, language: Language) -> str:
    DiscoveredFile(path, 0, language)
    return _stable_id("arctrellis-file-v1", "FILE", language.value, path)
