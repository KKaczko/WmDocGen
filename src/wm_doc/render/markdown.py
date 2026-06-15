from __future__ import annotations

from jinja2 import Template

from wm_doc.ir import InventoryResult

_TEMPLATE = Template(
    """# webMethods Fixture Inventory

Schema: `{{ inv.schema_version }}`

Scan root: `{{ inv.scan_root }}`

## File Summary

| Extension | Count |
| --- | ---: |
{% for item in inv.file_summary -%}
| `{{ item.extension }}` | {{ item.count }} |
{% endfor %}

## Packages

{% for package in inv.packages -%}
### {{ package.name }}

Root: `{{ package.root }}`

{% if package.aliases -%}
Aliases/conflicting names: {{ package.aliases | join(", ") }}

{% endif -%}
{% if package.manifest -%}
Manifest version: `{{ package.manifest.get("version") }}`

{% endif -%}
| Artifact | Type | Status |
| --- | --- | --- |
{% for artifact in package.artifacts -%}
| `{{ artifact.relative_path }}` | `{{ artifact.probable_type }}` | {{ artifact.status }} |
{% endfor %}

{% if package.findings -%}
Findings:

{% for finding in package.findings -%}
- {{ finding.status }} `{{ finding.code }}` at `{{ finding.source.path }}`: {{ finding.message }}
{% endfor %}

{% endif -%}
{% endfor -%}
{% if inv.findings -%}
## Global Findings

{% for finding in inv.findings -%}
- {{ finding.status }} `{{ finding.code }}` at `{{ finding.source.path }}`: {{ finding.message }}
{% endfor %}
{% endif -%}
""",
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_inventory_markdown(inventory: InventoryResult) -> str:
    return _TEMPLATE.render(inv=inventory)
