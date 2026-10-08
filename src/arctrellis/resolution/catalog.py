"""Path-based candidate discovery without filesystem or environment lookup."""

from pathlib import PurePosixPath

from arctrellis.core import CodeEntity

_SCRIPT_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")


def _python_aliases(path: str) -> tuple[str, ...]:
    p = PurePosixPath(path)
    parts = list(p.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    if any(not part.isidentifier() for part in parts):
        return ()
    aliases = [".".join(parts)] if parts else []
    if parts and parts[0] == "src" and len(parts) > 1:
        aliases.append(".".join(parts[1:]))
    return tuple(aliases)


def _python_candidates(site: CodeEntity, aliases: dict[str, set[str]]) -> tuple[tuple[str, ...], str]:
    metadata = dict(site.metadata)
    name = metadata.get("module", "")
    try:
        level = int(metadata.get("relative_level", "0"))
    except ValueError:
        return (), "invalid_import_metadata"
    if level < 0 or name.startswith(".") != (level > 0):
        return (), "invalid_import_metadata"
    names = {name}
    if level:
        if site.location is None:
            return (), "invalid_import_metadata"
        current = site.location.file_path
        names = set()
        for alias in _python_aliases(current):
            package = alias.split(".")
            if PurePosixPath(current).stem != "__init__":
                package.pop()
            if level > len(package):
                continue
            base = package[: len(package) - level + 1]
            suffix = name.lstrip(".")
            names.add(".".join(base + ([suffix] if suffix else [])))
    candidates = tuple(sorted({i for n in names for i in aliases.get(n, ())}))
    return candidates, "module_not_found"


def _script_candidates(site: CodeEntity, paths: dict[str, set[str]]) -> tuple[tuple[str, ...], str]:
    metadata = dict(site.metadata)
    literal = metadata.get("module_literal", "")
    if len(literal) < 2 or literal[0] not in "\"'" or literal[-1] != literal[0] or "\\" in literal:
        return (), "escaped_or_dynamic_literal"
    specifier = literal[1:-1]
    if not specifier.startswith(("./", "../")):
        return (), "non_relative_specifier"
    if site.location is None or any(ord(c) < 32 for c in specifier) or any(c in specifier for c in ":?#%"):
        return (), "unsupported_specifier"
    components = list(PurePosixPath(site.location.file_path).parent.parts)
    for component in specifier.split("/"):
        if component in ("", "."):
            continue
        if component == "..":
            if not components:
                return (), "outside_root"
            components.pop()
        else:
            components.append(component)
    base = "/".join(components)
    suffix = PurePosixPath(base).suffix
    index_path = base + "/index" if base else "index"
    directory_intent = specifier.endswith("/") or specifier.split("/")[-1] in (".", "..")
    if directory_intent:
        probes = tuple(index_path + ext for ext in _SCRIPT_EXTENSIONS)
    elif suffix.lower() in _SCRIPT_EXTENSIONS:
        probes = (base,)
    elif suffix:
        return (), "unsupported_extension"
    else:
        probes = tuple(base + ext for ext in _SCRIPT_EXTENSIONS) + tuple(index_path + ext for ext in _SCRIPT_EXTENSIONS)
    return tuple(sorted({i for p in probes for i in paths.get(p, ())})), "module_not_found"


def _catalog(modules: tuple[CodeEntity, ...]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    python: dict[str, set[str]] = {}
    script: dict[str, set[str]] = {}
    for module in modules:
        if module.location is None:
            raise ValueError("indexed module requires a source location")
        path = module.location.file_path
        if module.language == "python":
            for alias in _python_aliases(path):
                python.setdefault(alias, set()).add(module.id)
        elif module.language in ("javascript", "typescript"):
            script.setdefault(path, set()).add(module.id)
    return python, script
