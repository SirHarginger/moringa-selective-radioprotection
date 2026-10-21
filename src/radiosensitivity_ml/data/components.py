"""Connected components of related cell-line records (pure functions, no I/O).

Nodes are typed strings so different namespaces never collide:
``ACH:ACH-000019`` (DepMap model), ``CVCL:CVCL_0031`` (Cellosaurus accession),
``PATIENT:PT-xxxx`` (DepMap PatientID). Edges come from identifiers and
relationships only, never from outcome values.

A component is the transitive closure of all edges. Component IDs are deterministic:
``G:<smallest node in the component>``, so the same inputs always give the same IDs
regardless of input order.
"""

from __future__ import annotations

from collections.abc import Iterable


def ach_node(model_id: str) -> str:
    """Node name for a DepMap model ID."""
    return f"ACH:{model_id}"


def cvcl_node(accession: str) -> str:
    """Node name for a Cellosaurus accession."""
    return f"CVCL:{accession}"


def patient_node(patient_id: str) -> str:
    """Node name for a DepMap PatientID."""
    return f"PATIENT:{patient_id}"


def connected_components(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> dict[str, str]:
    """Return ``{node: component_id}`` for all nodes (edge endpoints are added as nodes)."""
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != root:  # path compression
            parent[node], node = root, parent[node]
        return root

    def add(node: str) -> None:
        parent.setdefault(node, node)

    for node in nodes:
        add(node)
    for left, right in edges:
        add(left)
        add(right)
        a, b = find(left), find(right)
        if a != b:
            # attach the larger root under the smaller one: roots stay minimal
            parent[max(a, b)] = min(a, b)
    members: dict[str, list[str]] = {}
    for node in parent:
        members.setdefault(find(node), []).append(node)
    return {node: f"G:{min(group)}" for group in members.values() for node in sorted(group)}


def component_members(assignment: dict[str, str]) -> dict[str, tuple[str, ...]]:
    """Invert ``{node: component}`` into ``{component: sorted nodes}`` (sorted by ID)."""
    groups: dict[str, list[str]] = {}
    for node, component in assignment.items():
        groups.setdefault(component, []).append(node)
    return {component: tuple(sorted(groups[component])) for component in sorted(groups)}
