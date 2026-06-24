# wm-doc Technical Documentation

This index is generated from static analysis. Process names and descriptions, when present, come from `processes.yml`.

## Generated Inventory

| Area | Count |
| --- | ---: |
| Services | 35 |
| Document Types | 7 |
| Process definitions | 0 |
| Technical entrypoint candidates | 15 |
| Service dependency edges | 86 |
| Document dependency edges | 5 |

## Links

- [Analysis JSON](analysis.json)
- [Graph catalog](graphs/index.md)
- Service dependency graph: [SVG](graphs/dependencies.svg) ([DOT](graphs/dependencies.dot))
- Document dependency graph: [SVG](graphs/documents.svg) ([DOT](graphs/documents.dot))
- [Technical entrypoint candidates](entrypoints.md)
- [Services](services/)
- [Document Types](documents/)
- Process catalog: no process definitions were declared.

## Disclosure Policy

- Free text mode: include
- Literal mode: redact
- Secret guard: enabled
- Secret guard strategy: secret-guard.v1

## Limitations

Process membership is generated from declared entrypoints and static service dependency evidence. The tool does not infer business meaning, runtime order, JDBC/UM/JMS resources, trigger behavior, scheduler behavior, or deep Java effects.
