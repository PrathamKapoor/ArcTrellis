"""Synthetic repositories at scale for bounded-behavior testing.

The generated text is untrusted static data. Nothing here is imported, executed
or installed; the fixtures exist only so traversal limits, retrieval budgets,
response size and determinism can be exercised on a graph far larger than the
mixed-language fixture (D-149).
"""

from __future__ import annotations

MAX_SOURCE_NAME = 12


def _module_name(index: int) -> str:
    return f"mod{index:03d}"


def build_python_sources(module_count: int, functions_per_module: int) -> dict[str, str]:
    """Generate modules with repeated function names and dense intra-module calls.

    Every module defines the same set of function names, so qualified-name and
    name-level ambiguity exist at scale. Each module's entry function calls every
    other function in the same module, and the final module closes a cycle back
    to the first.
    """
    sources: dict[str, str] = {}
    names = [f"handler{index}" for index in range(functions_per_module)]
    for module_index in range(module_count):
        lines = [f"def {names[0]}(target):", "    return step(target)"]
        for position, name in enumerate(names[1:], start=1):
            lines.append("")
            lines.append("")
            lines.append(f"def {name}(value):")
            if position == 1:
                lines.append(f"    return {names[0]}(value) + 1")
            else:
                lines.append(f"    return {names[position - 1]}(value) + {position}")
        if module_index > 0:
            lines.append("")
            lines.append("")
            lines.append("def previousModuleEntry(value):")
            lines.append(f"    return bridge{module_index - 1}(value)")
        sources[f"{_module_name(module_index)}.py"] = "\n".join(lines) + "\n"
    return sources


def build_endpoint_sources(endpoint_count: int) -> dict[str, str]:
    """Generate Express routes whose paths deliberately repeat.

    Half the routes share one method and path, so endpoint selection must report
    ambiguity rather than choose, at a scale where guessing would be easy.
    """
    handlers = "\n\n".join(
        f"function persist{index}(req, res) {{ return persist{index - 1}(req, res); }}"
        for index in range(1, endpoint_count)
    )
    lines = [
        'import express from "express";',
        'import { PrismaClient } from "@prisma/client";',
        "const app = express();",
        "const db = new PrismaClient();",
        "function seed(value) { return db.payment.create({ data: { amount: value } }); }",
        handlers,
    ]
    for index in range(endpoint_count):
        lines.append(f'app.post("/payments", persist{index});')
    lines.append('app.post("/payments", seed);')
    return {"scale/app.js": "\n".join(lines) + "\n"}


def build_high_degree_sources(degree: int) -> dict[str, str]:
    """Generate one hub callable with a very large outgoing and incoming degree."""
    blocks = ["def hub(value):", "    return value", "", ""]
    for index in range(degree):
        blocks.extend([f"def caller{index}(value):", f"    return hub(value) + {index}", "", ""])
    return {"scale/hub.py": "\n".join(blocks).rstrip() + "\n"}


def build_cycle_sources(length: int) -> dict[str, str]:
    """Generate one import cycle so traversal termination is exercised."""
    lines: list[str] = []
    for index in range(length):
        lines.append(f"def node{index}(value):")
        lines.append(f"    return node{(index + 1) % length}(value)")
        lines.append("")
        lines.append("")
    return {"scale/cycle.py": "\n".join(lines).rstrip() + "\n"}


def build_large_repository(
    module_count: int = 60,
    functions_per_module: int = 12,
    endpoint_count: int = 40,
    hub_degree: int = 120,
    cycle_length: int = 30,
) -> dict[str, str]:
    """Compose one repository that is large, ambiguous, cyclic and high-degree."""
    sources = build_python_sources(module_count, functions_per_module)
    sources.update(build_endpoint_sources(endpoint_count))
    sources.update(build_high_degree_sources(hub_degree))
    sources.update(build_cycle_sources(cycle_length))
    return sources
