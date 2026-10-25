import "@xyflow/react/dist/style.css";

import type { Edge, Node } from "@xyflow/react";
import { Controls, MarkerType, ReactFlow } from "@xyflow/react";
import { useId, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";

import type { GraphTarget, SearchService } from "../../contract";
import { useExplorer } from "../../data/explorer-context";
import { useResource } from "../../data/use-resource";
import type { GraphIndex, GraphModel, ModelNode } from "../../domain/graph";
import { buildNeighborhood, indexGraph, neighbours } from "../../domain/graph";
import type { Box } from "../../domain/layout";
import { layoutModel } from "../../domain/layout";
import { SectionHeading } from "../SectionHeading";
import { NODE_TYPES } from "./GraphNodes";
import type { MoreNode, ServiceNode, TargetNode } from "./GraphNodes";
import type { GraphSettings } from "./graph-params";
import {
  DEPTHS,
  LIMITS,
  MAX_PER_NODE,
  readSettings,
  serviceGraphPath,
  settingsQuery,
} from "./graph-params";

const KIND_TAG: Record<SearchService["kind"], string> = {
  flow: "FLOW",
  java: "Java",
  adapter: "JDBC adapter",
  opaque: "other type",
};
const ANALYSIS_TAG: Record<SearchService["analysis"], string> = {
  full: "",
  partial: ", partly analysed",
  opaque: ", not analysed",
};
const TARGET_TAG: Record<GraphTarget["status"], string> = {
  resolved: "several services share this name",
  platform: "built-in",
  outside: "outside the analysed packages",
  unresolved: "unresolved",
  dynamic: "decided at run time",
  unsupported: "not interpreted",
};

/** The bounded call graph around one service. */
export function GraphPanel({ focalId, focalName }: { focalId: string; focalName: string }) {
  const { repository, search } = useExplorer();
  const graph = useResource(() => repository.graph(), "graph");
  const data = graph.status === "ready" ? graph.data : null;
  const index = useMemo(() => (data === null ? null : indexGraph(data, search)), [data, search]);
  const focal = index?.nodeOf(focalId);

  return (
    <section className="section graph-section" aria-labelledby="graph-title">
      <SectionHeading id="graph-title" source="analysis">
        Call graph
      </SectionHeading>
      {graph.status === "error" ? (
        <p className="status-line error" role="alert">
          {graph.error.message}
        </p>
      ) : index === null || focal === undefined ? (
        <p className="muted" role="status">
          Loading the call graph…
        </p>
      ) : (
        <GraphView index={index} focal={focal} focalName={focalName} />
      )}
    </section>
  );
}

function GraphView({
  index,
  focal,
  focalName,
}: {
  index: GraphIndex;
  focal: number;
  focalName: string;
}) {
  const [params, setParams] = useSearchParams();
  const settings = readSettings(params);
  const [expanded, setExpanded] = useState<ReadonlySet<number>>(() => new Set());
  const [listFor, setListFor] = useState<{ owner: number; side: "caller" | "callee" } | null>(null);
  const model = useMemo(
    () =>
      buildNeighborhood(index, focal, {
        depth: settings.depth,
        direction: settings.direction,
        maxNodes: settings.limit,
        maxPerNode: MAX_PER_NODE,
        platform: settings.builtins,
        expanded,
      }),
    [index, focal, settings.depth, settings.direction, settings.limit, settings.builtins, expanded],
  );
  const update = (change: Partial<GraphSettings>) => {
    setListFor(null);
    setParams(settingsQuery({ ...settings, ...change }, params));
  };
  const toggle = (node: number) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(node)) next.delete(node);
      else next.add(node);
      return next;
    });
  };
  const shownServices = model.nodes.filter(
    (node) => node.type === "node" && index.isService(node.node),
  ).length;
  const shownTargets = model.nodes.filter(
    (node) => node.type === "node" && !index.isService(node.node),
  ).length;

  return (
    <>
      <GraphControls settings={settings} update={update} onReset={() => setExpanded(new Set())} />
      <p className="note" role="status">
        {shownServices} service{shownServices === 1 ? "" : "s"}
        {shownTargets > 0
          ? ` and ${String(shownTargets)} other call target${shownTargets === 1 ? "" : "s"}`
          : ""}{" "}
        shown around <code>{focalName}</code>.
        {model.limitReached
          ? " The node limit was reached, so some neighbours are not shown: raise the limit or open a service to centre on it."
          : ""}
      </p>
      {settings.view === "graph" ? (
        <GraphCanvas
          index={index}
          model={model}
          settings={settings}
          focalName={focalName}
          signature={`${String(focal)}|${[...expanded].sort().join(",")}|${params.toString()}`}
          onToggle={toggle}
          onMore={(owner, side) => setListFor({ owner, side })}
        />
      ) : (
        <GraphList
          index={index}
          model={model}
          settings={settings}
          onMore={(owner, side) => setListFor({ owner, side })}
        />
      )}
      {settings.view === "graph" ? (
        <MoreButtons
          index={index}
          model={model}
          onMore={(owner, side) => setListFor({ owner, side })}
        />
      ) : null}
      {listFor !== null ? (
        <NeighbourList
          index={index}
          settings={settings}
          {...listFor}
          onClose={() => setListFor(null)}
        />
      ) : null}
      {settings.view === "graph" ? <Legend /> : null}
    </>
  );
}

function GraphControls({
  settings,
  update,
  onReset,
}: {
  settings: GraphSettings;
  update: (change: Partial<GraphSettings>) => void;
  onReset: () => void;
}) {
  const id = useId();
  return (
    <div className="graph-controls">
      <label htmlFor={`${id}-depth`}>
        Depth{" "}
        <select
          id={`${id}-depth`}
          value={settings.depth}
          onChange={(event) => update({ depth: Number(event.target.value) })}
        >
          {DEPTHS.map((depth) => (
            <option key={depth} value={depth}>
              {depth}
            </option>
          ))}
        </select>
      </label>
      <label htmlFor={`${id}-direction`}>
        Show{" "}
        <select
          id={`${id}-direction`}
          value={settings.direction}
          onChange={(event) =>
            update({ direction: event.target.value as GraphSettings["direction"] })
          }
        >
          <option value="both">callers and callees</option>
          <option value="callees">callees</option>
          <option value="callers">callers</option>
        </select>
      </label>
      <label htmlFor={`${id}-limit`}>
        Node limit{" "}
        <select
          id={`${id}-limit`}
          value={settings.limit}
          onChange={(event) => update({ limit: Number(event.target.value) })}
        >
          {LIMITS.map((limit) => (
            <option key={limit} value={limit}>
              {limit}
            </option>
          ))}
        </select>
      </label>
      <label htmlFor={`${id}-builtins`} className="graph-check">
        <input
          id={`${id}-builtins`}
          type="checkbox"
          checked={settings.builtins}
          onChange={(event) => update({ builtins: event.target.checked })}
        />{" "}
        Built-in services
      </label>
      <button
        type="button"
        onClick={() => update({ view: settings.view === "graph" ? "list" : "graph" })}
      >
        {settings.view === "graph" ? "Show as list" : "Show as graph"}
      </button>
      <button type="button" onClick={onReset}>
        Close opened levels
      </button>
    </div>
  );
}

function GraphCanvas({
  index,
  model,
  settings,
  focalName,
  signature,
  onToggle,
  onMore,
}: {
  index: GraphIndex;
  model: GraphModel;
  settings: GraphSettings;
  focalName: string;
  signature: string;
  onToggle: (node: number) => void;
  onMore: (owner: number, side: "caller" | "callee") => void;
}) {
  const labels = useMemo(
    () => new Map(model.nodes.map((node) => [node.key, layoutLabel(index, node)])),
    [index, model],
  );
  const boxes = useMemo(() => layoutModel(model, (key) => labels.get(key) ?? key), [model, labels]);
  const nodes = model.nodes.map((node): ServiceNode | TargetNode | MoreNode => {
    const box = boxes.get(node.key) ?? { x: 0, y: 0, width: 160, height: 48 };
    const base = {
      id: node.key,
      position: { x: box.x, y: box.y },
      width: box.width,
      height: box.height,
    };
    if (node.type === "more") {
      return {
        ...base,
        type: "more",
        data: {
          label: `+${String(node.hidden)} more ${node.side === "caller" ? "callers" : "callees"}`,
          onOpen: () => onMore(node.owner, node.side),
        },
      };
    }
    const service = index.services[node.node];
    if (service !== undefined && index.isService(node.node)) {
      return {
        ...base,
        type: "service",
        data: {
          name: service.name,
          shortName: service.name.slice(service.name.lastIndexOf(":") + 1),
          namespace: service.name.slice(0, service.name.lastIndexOf(":")),
          path: serviceGraphPath(service.name, settings),
          className: `kind-${service.kind} analysis-${service.analysis}`,
          tag: `${KIND_TAG[service.kind]}${ANALYSIS_TAG[service.analysis]}`,
          focal: node.side === "focal",
          expandable: node.expandable,
          expanded: node.expanded,
          onToggle: () => onToggle(node.node),
        },
      };
    }
    const target = index.target(node.node);
    return {
      ...base,
      type: "target",
      data: {
        name: index.name(node.node),
        className: `status-${target?.status ?? "unresolved"}`,
        tag: target === undefined ? "" : TARGET_TAG[target.status],
        note: target?.note ?? null,
      },
    };
  });
  const edges: Edge[] = model.edges.map((edge) => ({
    id: edge.key,
    source: edge.source,
    target: edge.target,
    ...edgeHandles(boxes.get(edge.source), boxes.get(edge.target)),
    className: `graph-edge relation-${edge.relation}`,
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
  }));
  return (
    <div className="graph-canvas" role="group" aria-label={`Call graph around ${focalName}`}>
      <ReactFlow
        key={signature}
        nodes={nodes as Node[]}
        edges={edges}
        nodeTypes={NODE_TYPES}
        fitView
        // Large fan-outs stay readable: the view never zooms out below 55%; pan to see more.
        fitViewOptions={{ padding: 0.12, maxZoom: 1, minZoom: 0.55 }}
        minZoom={0.1}
        maxZoom={1.5}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        nodesFocusable={false}
        edgesFocusable={false}
        // The wheel scrolls the page; zoom with the buttons or a pinch.
        zoomOnScroll={false}
        preventScrolling={false}
        colorMode="system"
        proOptions={{ hideAttribution: true }}
      >
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

/** Right to left normally; bottom to top between nodes of one column (no loops back). */
function edgeHandles(
  source: Box | undefined,
  target: Box | undefined,
): { sourceHandle: string; targetHandle: string } {
  if (source !== undefined && target !== undefined) {
    const sameColumn = Math.abs(source.x + source.width / 2 - (target.x + target.width / 2)) < 1;
    if (sameColumn) {
      return source.y < target.y
        ? { sourceHandle: "bottom-out", targetHandle: "top-in" }
        : { sourceHandle: "top-out", targetHandle: "bottom-in" };
    }
  }
  return { sourceHandle: "right", targetHandle: "left" };
}

/** Text whose length estimates a node's width (the namespace line is smaller type). */
function layoutLabel(index: GraphIndex, node: ModelNode): string {
  if (node.type === "more") return "+000 more callers";
  const name = index.name(node.node);
  if (!index.isService(node.node)) return name;
  const colon = name.lastIndexOf(":");
  const short = name.slice(colon + 1);
  const meta = Math.ceil((colon + 12) * 0.8);
  return short.length >= meta ? short : "x".repeat(meta);
}

/** "+N more" as buttons outside the canvas too: always reachable, even when panned away. */
function MoreButtons({
  index,
  model,
  onMore,
}: {
  index: GraphIndex;
  model: GraphModel;
  onMore: (owner: number, side: "caller" | "callee") => void;
}) {
  const more = model.nodes.filter((node) => node.type === "more");
  if (more.length === 0) return null;
  return (
    <div className="graph-more-list">
      {more.map((node) =>
        node.type === "more" ? (
          <button key={node.key} type="button" onClick={() => onMore(node.owner, node.side)}>
            +{node.hidden} more {node.side === "caller" ? "callers" : "callees"} of{" "}
            {index.name(node.owner)}
          </button>
        ) : null,
      )}
    </div>
  );
}

/** The same neighbourhood as nested lists, for keyboard and screen-reader use. */
function GraphList({
  index,
  model,
  settings,
  onMore,
}: {
  index: GraphIndex;
  model: GraphModel;
  settings: GraphSettings;
  onMore: (owner: number, side: "caller" | "callee") => void;
}) {
  const groups = (["caller", "callee"] as const).map((side) => {
    const nodes = model.nodes.filter((node) => node.type === "node" && node.side === side);
    const depths = [...new Set(nodes.map((node) => (node.type === "node" ? node.depth : 0)))].sort(
      (a, b) => a - b,
    );
    return { side, nodes, depths };
  });
  return (
    <div className="graph-list">
      {groups.map(({ side, nodes, depths }) => (
        <div key={side}>
          <h3>{side === "caller" ? "Callers" : "Callees"}</h3>
          {nodes.length === 0 ? <p className="muted">None shown.</p> : null}
          <ul>
            {depths.map((depth) => (
              <li key={depth}>
                {depth === 1 ? "Direct" : `${String(depth)} steps away`}
                <ul>
                  {nodes
                    .filter((node) => node.type === "node" && node.depth === depth)
                    .map((node) =>
                      node.type === "node" ? (
                        <li key={node.key}>
                          <NodeLink index={index} node={node.node} settings={settings} />
                        </li>
                      ) : null,
                    )}
                </ul>
              </li>
            ))}
          </ul>
          {model.nodes
            .filter((node) => node.type === "more" && node.side === side)
            .map((node) =>
              node.type === "more" ? (
                <button key={node.key} type="button" onClick={() => onMore(node.owner, node.side)}>
                  +{node.hidden} more {side === "caller" ? "callers" : "callees"} of{" "}
                  {index.name(node.owner)}
                </button>
              ) : null,
            )}
        </div>
      ))}
    </div>
  );
}

function NeighbourList({
  index,
  settings,
  owner,
  side,
  onClose,
}: {
  index: GraphIndex;
  settings: GraphSettings;
  owner: number;
  side: "caller" | "callee";
  onClose: () => void;
}) {
  const items = neighbours(
    index,
    owner,
    side === "caller" ? "callers" : "callees",
    settings.builtins,
  );
  const id = useId();
  return (
    <section className="neighbour-list" aria-labelledby={id}>
      <h3 id={id}>
        All {items.length} {side === "caller" ? "callers" : "callees"} of{" "}
        <code>{index.name(owner)}</code>
      </h3>
      <ul className="link-list">
        {items.map((item) => (
          <li key={item.node}>
            <NodeLink index={index} node={item.node} settings={settings} />
          </li>
        ))}
      </ul>
      <button type="button" onClick={onClose}>
        Close the list
      </button>
    </section>
  );
}

function NodeLink({
  index,
  node,
  settings,
}: {
  index: GraphIndex;
  node: number;
  settings: GraphSettings;
}) {
  const name = index.name(node);
  if (!index.isService(node)) {
    const target = index.target(node);
    return (
      <>
        <code>{name}</code>{" "}
        <span className="muted">({target === undefined ? "" : TARGET_TAG[target.status]})</span>
      </>
    );
  }
  return (
    <Link to={serviceGraphPath(name, settings)} className="code-link">
      <code>{name}</code>
    </Link>
  );
}

function Legend() {
  return (
    <ul className="graph-legend" aria-label="Legend">
      <li>
        <span className="swatch focal" /> this service
      </li>
      <li>
        <span className="swatch analysis-full" /> analysed service
      </li>
      <li>
        <span className="swatch analysis-partial" /> partly analysed
      </li>
      <li>
        <span className="swatch analysis-opaque" /> not analysed (adapter, other)
      </li>
      <li>
        <span className="swatch status-platform" /> built-in
      </li>
      <li>
        <span className="swatch status-outside" /> outside the analysed packages
      </li>
      <li>
        <span className="swatch status-dynamic" /> decided at run time or unresolved
      </li>
      <li>
        <span className="swatch more" /> more neighbours (opens a list)
      </li>
    </ul>
  );
}
