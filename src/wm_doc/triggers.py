"""Trigger details from a trigger's node.ndf (owner-approved reader, M12).

Read from the `trigger` record of a `webMethods/trigger` node:

- `trigger_type`: `jms-trigger` (JMS) or `broker-trigger` (webMethods messaging: Broker or
  Universal Messaging);
- JMS triggers: the connection alias (`aliasName`), the destinations (`destinations[]`
  with `destination` and `destinationType`, 0 = queue, 1 = topic) and the routing rules'
  handler services (`routingRules[]/serviceName`);
- messaging triggers: per condition the subscribed document type
  (`conditions[]/data/messageTypeFilterPair/messageType`) and the handler service
  (`conditions[]/data/serviceName`).

Filters, message selectors, execution users and tuning values are never read. Every kept
value must look like a name; anything else is dropped.
"""

from __future__ import annotations

import re
from typing import Any

from wm_doc.ir import TriggerDestination, TriggerDetails, TriggerSubscription
from wm_doc.values import ValuesData, record_value, scalar_value

TRIGGER_NODE_TYPE = "webMethods/trigger"
TRIGGER_KINDS = {
    "jms-trigger": "JMS trigger",
    "broker-trigger": "webMethods messaging trigger",
}
DESTINATION_KINDS = {"0": "queue", "1": "topic"}
MAX_ITEMS = 50
MAX_NAME_LENGTH = 200
_FULL_NAME_RE = re.compile(r"^[\w.$-]+:[\w.$-]+$")
# JMS destination and alias names: printable, no whitespace runs, no URL or credential syntax.
_PLAIN_NAME_RE = re.compile(r"^[\w.$#/\-]+$")


def read_trigger(values: ValuesData) -> TriggerDetails | None:
    """Trigger details, or None when the node is not a trigger."""
    if scalar_value(values, "node_type") != TRIGGER_NODE_TYPE:
        return None
    trigger_type = _clean(scalar_value(values, "trigger_type"), _PLAIN_NAME_RE)
    body = record_value(values, "trigger") or {}
    destinations: list[TriggerDestination] = []
    for item in _records(body.get("destinations")):
        name = _clean(scalar_value(item, "destination"), _PLAIN_NAME_RE)
        if name is None:
            continue
        kind = DESTINATION_KINDS.get(str(item.get("destinationType") or "").strip())
        destination = TriggerDestination(name=name, kind=kind or "not determined")
        if destination not in destinations:
            destinations.append(destination)
    subscriptions: list[TriggerSubscription] = []
    for rule in _records(body.get("routingRules")):
        _add(subscriptions, scalar_value(rule, "serviceName"), None)
    for condition in _records(body.get("conditions")):
        data = record_value(condition, "data") or condition
        pair = record_value(data, "messageTypeFilterPair") or {}
        _add(subscriptions, scalar_value(data, "serviceName"), scalar_value(pair, "messageType"))
    # Older JMS triggers name their single handler directly.
    _add(subscriptions, scalar_value(body, "serviceName"), None)
    return TriggerDetails(
        trigger_type=trigger_type,
        kind=TRIGGER_KINDS.get(trigger_type or "", "trigger"),
        connection_alias=_clean(scalar_value(body, "aliasName"), _PLAIN_NAME_RE),
        destinations=destinations[:MAX_ITEMS],
        subscriptions=subscriptions[:MAX_ITEMS],
    )


def trigger_summary(details: TriggerDetails) -> str:
    """One line for entry points: what the trigger listens to."""
    parts: list[str] = []
    if details.destinations:
        parts.append(
            ", ".join(
                f"{d.kind} `{d.name}`" if d.kind != "not determined" else f"`{d.name}`"
                for d in details.destinations[:3]
            )
        )
    documents = sorted(
        {s.document_type for s in details.subscriptions if s.document_type}, key=str.casefold
    )
    if documents:
        parts.append("document " + ", ".join(f"`{name}`" for name in documents[:3]))
    if details.connection_alias:
        parts.append(f"JMS alias `{details.connection_alias}`")
    return "; ".join(parts)


def _add(
    subscriptions: list[TriggerSubscription], handler: str | None, document: str | None
) -> None:
    item = TriggerSubscription(
        handler=_clean(handler, _FULL_NAME_RE), document_type=_clean(document, _FULL_NAME_RE)
    )
    if (item.handler or item.document_type) and item not in subscriptions:
        subscriptions.append(item)


def _records(value: Any) -> list[ValuesData]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _clean(value: str | None, pattern: re.Pattern[str]) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text or len(text) > MAX_NAME_LENGTH or not pattern.match(text):
        return None
    return text
