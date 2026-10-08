"""One unresolved Python import binding per normalized clause."""

from dataclasses import dataclass

from arctrellis.parsing import SyntaxNode
from .source import _PythonSource


@dataclass(frozen=True, slots=True)
class _ImportBinding:
    node: SyntaxNode
    name: str
    metadata: tuple[tuple[str, str], ...]


def _module_text(source: _PythonSource, node: SyntaxNode) -> str:
    identifiers = [source.text(child) for child in node.walk() if child.kind == "identifier"]
    level = sum(source.text(child).count(".") for child in node.children if child.kind == "import_prefix")
    return "." * level + ".".join(identifiers)


def _import_bindings(source: _PythonSource, statement: SyntaxNode) -> tuple[_ImportBinding, ...] | None:
    future = statement.kind == "future_import_statement"
    form = "from" if statement.kind in ("import_from_statement", "future_import_statement") else "import"
    module_node = statement.child_by_field("module_name")
    if form == "from" and not future and (module_node is None or module_node.kind not in ("dotted_name", "relative_import")):
        return None
    module = "__future__" if future else (_module_text(source, module_node) if module_node else "")
    relative_level = len(module) - len(module.lstrip("."))
    clauses = [child for child in statement.children if child.field_name == "name" or child.kind == "wildcard_import"]
    bindings = []
    for clause in clauses:
        alias = ""
        wildcard = clause.kind == "wildcard_import"
        if wildcard:
            imported = "*"
        elif clause.kind == "aliased_import":
            name_node, alias_node = clause.child_by_field("name"), clause.child_by_field("alias")
            if name_node is None or alias_node is None or alias_node.kind != "identifier":
                return None
            imported, alias = _module_text(source, name_node), source.text(alias_node)
        elif clause.kind == "dotted_name":
            imported = _module_text(source, clause)
        else:
            return None
        if not imported or (form == "from" and "." in imported):
            return None
        binding = alias or (imported.split(".")[0] if form == "import" else imported)
        metadata = (("import_form", form), ("module", module if form == "from" else imported),
                    ("imported_name", imported if form == "from" else ""), ("alias", alias),
                    ("binding", binding), ("relative_level", str(relative_level)),
                    ("is_wildcard", "true" if wildcard else "false"))
        bindings.append(_ImportBinding(clause, binding, metadata))
    return tuple(bindings) if bindings else None
