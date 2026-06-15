from __future__ import annotations

import json

from wm_doc.ir import InventoryResult


def render_inventory_json(inventory: InventoryResult) -> str:
    payload = inventory.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
