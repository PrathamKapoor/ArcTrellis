"""Static ES import clauses; literal spelling is retained, never evaluated."""

from dataclasses import dataclass

from arctrellis.parsing import SyntaxNode


@dataclass(frozen=True, slots=True)
class _ScriptImport:
    node: SyntaxNode
    name: str
    metadata: tuple[tuple[str, str], ...]


def _literal(source, node: SyntaxNode) -> str | None:
    if node.kind != 'string':
        return None
    text = source.text(node)
    if len(text) < 2 or text[0] not in ('"', "'") or text[-1] != text[0]:
        return None
    # The exact interior is source spelling, not a cooked runtime string.
    return text[1:-1]


def _binding(source, node, name, form, module, literal, imported, binding, type_only=False, alias=''):
    return _ScriptImport(node, name, (
        ('import_form', form), ('module', module), ('module_literal', literal),
        ('imported_name', imported), ('alias', alias), ('binding', binding),
        ('is_type_only', str(type_only).lower()), ('module_format', 'source_spelling')))


def _es_imports(source, statement: SyntaxNode) -> tuple[_ScriptImport, ...] | None:
    module_node = statement.child_by_field('source')
    if module_node is None:
        return None
    module = _literal(source, module_node)
    if module is None:
        return None
    literal = source.text(module_node)
    clause = next((c for c in statement.children if c.kind == 'import_clause'), None)
    if clause is None:
        # JSON-quoted spelling handles empty/padded module names without fake bindings.
        name = module if module and module.strip() == module else literal
        return (_binding(source, module_node, name, 'side_effect', module, literal, '', ''),)
    type_only = 'type' in source.words_before(statement, clause)
    bindings = []
    for child in clause.children:
        if child.kind == 'identifier':
            name = source.text(child)
            bindings.append(_binding(source, child, name, 'default', module, literal, 'default', name, type_only))
        elif child.kind == 'namespace_import':
            identifier = next((c for c in child.children if c.kind == 'identifier'), None)
            if identifier is None:
                return None
            name = source.text(identifier)
            bindings.append(_binding(source, child, name, 'namespace', module, literal, '*', name, type_only))
        elif child.kind == 'named_imports':
            for specifier in child.children:
                if specifier.kind == 'comment':
                    continue
                original = specifier.child_by_field('name')
                alias = specifier.child_by_field('alias')
                if original is None or (alias is not None and alias.kind != 'identifier'):
                    return None
                name = source.text(alias or original)
                only = type_only or 'type' in source.words_before(specifier, original)
                bindings.append(_binding(source, specifier, name, 'named', module, literal,
                                         source.text(original), name, only, source.text(alias) if alias else ''))
    if not bindings:
        name = module if module and module.strip() == module else literal
        return (_binding(source, module_node, name, 'side_effect', module, literal, '', '', type_only),)
    return tuple(bindings)


def _require_import(source, declarator: SyntaxNode) -> _ScriptImport | None:
    name, value = declarator.child_by_field('name'), declarator.child_by_field('value')
    if name is None or name.kind != 'identifier' or value is None or value.kind != 'call_expression':
        return None
    callee, arguments = value.child_by_field('function'), value.child_by_field('arguments')
    if callee is None or callee.kind != 'identifier' or source.text(callee) != 'require' or arguments is None:
        return None
    args = tuple(c for c in arguments.children if c.kind != 'comment')
    if len(args) != 1:
        return None
    module = _literal(source, args[0])
    if module is None or '\\' in module:
        return None
    binding = source.text(name)
    return _binding(source, declarator, binding, 'require', module, source.text(args[0]), '', binding)
