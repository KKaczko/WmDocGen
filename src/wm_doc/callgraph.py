"""Call-graph ordering shared by the effects analysis and the summarizer."""

from __future__ import annotations

from collections.abc import Iterable

from wm_doc.ir import FlowService


def summary_order(services: Iterable[FlowService]) -> list[str]:
    """Order services so that every local callee comes before its callers.

    Uses Tarjan's strongly-connected-components algorithm, which emits components in
    reverse topological order of the call graph: callees first. Services in a call cycle
    share a component and are ordered by name; inside a cycle some callee descriptions
    are necessarily unavailable.
    """
    by_name = {service.identity.full_name: service for service in services}
    graph: dict[str, list[str]] = {}
    for name, service in by_name.items():
        targets = {
            dependency.target_service
            for dependency in service.unique_dependencies
            if dependency.resolved
            and dependency.target_service in by_name
            and dependency.target_service != name
        }
        graph[name] = sorted(targets, key=str.casefold)

    index_of: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    order: list[str] = []
    counter = 0

    for root in sorted(graph, key=str.casefold):
        if root in index_of:
            continue
        # Iterative DFS: each frame is (node, iterator position over its neighbours).
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, position = work.pop()
            if position == 0:
                index_of[node] = lowlink[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            neighbours = graph[node]
            descended = False
            while position < len(neighbours):
                neighbour = neighbours[position]
                position += 1
                if neighbour not in index_of:
                    work.append((node, position))
                    work.append((neighbour, 0))
                    descended = True
                    break
                if neighbour in on_stack:
                    lowlink[node] = min(lowlink[node], index_of[neighbour])
            if descended:
                continue
            if lowlink[node] == index_of[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                order.extend(sorted(component, key=str.casefold))
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
    return order
