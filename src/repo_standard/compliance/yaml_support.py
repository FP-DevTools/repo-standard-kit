"""YAML loading helpers for GitHub-compatible keys and source locations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

# ruamel resolves the YAML 1.2 core schema, where only `true`/`false` are
# booleans, so a workflow's `on:` trigger key survives loading as a string.
_GITHUB_YAML = YAML(typ="safe")


@dataclass(frozen=True)
class YamlDocument:
    data: Any
    lines: dict[tuple[str | int, ...], int]

    def line(self, *path: str | int) -> int | None:
        return self.lines.get(tuple(path))


class YamlParseError(ValueError):
    def __init__(self, message: str, line: int | None, column: int | None) -> None:
        super().__init__(message)
        self.line = line
        self.column = column


def _node_lines(
    node: Node, path: tuple[str | int, ...], output: dict[tuple[str | int, ...], int]
) -> None:
    output[path] = node.start_mark.line + 1
    if isinstance(node, MappingNode):
        for key_node, value_node in node.value:
            if not isinstance(key_node, ScalarNode):
                continue
            child_path = (*path, key_node.value)
            output[child_path] = value_node.start_mark.line + 1
            _node_lines(value_node, child_path, output)
    elif isinstance(node, SequenceNode):
        for index, child in enumerate(node.value):
            _node_lines(child, (*path, index), output)


def load_github_yaml(text: str) -> YamlDocument:
    """Safely load YAML and retain best-effort line numbers for value nodes."""
    try:
        data = _GITHUB_YAML.load(text)
        node = _GITHUB_YAML.compose(text)
    except YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        line = mark.line + 1 if mark is not None else None
        column = mark.column + 1 if mark is not None else None
        raise YamlParseError(str(error), line, column) from error
    lines: dict[tuple[str | int, ...], int] = {}
    if node is not None:
        _node_lines(node, (), lines)
    return YamlDocument(data=data, lines=lines)
