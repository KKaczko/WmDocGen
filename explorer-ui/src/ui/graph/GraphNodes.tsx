import type { Node, NodeProps } from "@xyflow/react";
import { Handle, Position } from "@xyflow/react";
import { Link } from "react-router";

export interface ServiceNodeData extends Record<string, unknown> {
  readonly name: string;
  readonly shortName: string;
  readonly namespace: string;
  readonly path: string;
  readonly className: string;
  readonly tag: string;
  readonly focal: boolean;
  readonly expandable: boolean;
  readonly expanded: boolean;
  readonly onToggle: () => void;
}

export interface TargetNodeData extends Record<string, unknown> {
  readonly name: string;
  readonly className: string;
  readonly tag: string;
  readonly note: string | null;
}

export interface MoreNodeData extends Record<string, unknown> {
  readonly label: string;
  readonly onOpen: () => void;
}

export type ServiceNode = Node<ServiceNodeData, "service">;
export type TargetNode = Node<TargetNodeData, "target">;
export type MoreNode = Node<MoreNodeData, "more">;

/**
 * Connection points. React Flow finds them by the classes "source" and "target", so node
 * elements must never use those class names. Edges normally run right to left; between nodes
 * in the same column they run bottom to top so they do not loop back.
 */
function Handles() {
  return (
    <>
      <Handle id="left" type="target" position={Position.Left} isConnectable={false} />
      <Handle id="right" type="source" position={Position.Right} isConnectable={false} />
      <Handle id="top-in" type="target" position={Position.Top} isConnectable={false} />
      <Handle id="bottom-out" type="source" position={Position.Bottom} isConnectable={false} />
      <Handle id="bottom-in" type="target" position={Position.Bottom} isConnectable={false} />
      <Handle id="top-out" type="source" position={Position.Top} isConnectable={false} />
    </>
  );
}

/** An analysed service: its name opens its page; + / − opens or closes its neighbours. */
export function ServiceNodeView({ data }: NodeProps<ServiceNode>) {
  return (
    <div className={`graph-node ${data.className}${data.focal ? " focal" : ""}`}>
      <Handles />
      <div className="graph-node-main">
        {data.focal ? (
          <span className="graph-node-name" title={data.name}>
            {data.shortName}
          </span>
        ) : (
          <Link
            to={data.path}
            className="graph-node-name nodrag nopan"
            title={data.name}
            aria-label={`Open ${data.name}`}
          >
            {data.shortName}
          </Link>
        )}
        <span className="graph-node-meta">
          {data.tag} · {data.namespace}
        </span>
      </div>
      {data.expandable ? (
        <button
          type="button"
          className="graph-node-toggle nodrag nopan"
          aria-expanded={data.expanded}
          aria-label={`${data.expanded ? "Hide" : "Show"} the next level from ${data.name}`}
          onClick={data.onToggle}
        >
          {data.expanded ? "−" : "+"}
        </button>
      ) : null}
    </div>
  );
}

/** A call target that is not an analysed service: built-in, outside, run time. */
export function TargetNodeView({ data }: NodeProps<TargetNode>) {
  return (
    <div className={`graph-node call-target ${data.className}`} title={data.note ?? data.name}>
      <Handles />
      <div className="graph-node-main">
        <span className="graph-node-name">{data.name}</span>
        <span className="graph-node-meta">{data.tag}</span>
      </div>
    </div>
  );
}

/** Neighbours left out by the per-node cap; opens the full list. */
export function MoreNodeView({ data }: NodeProps<MoreNode>) {
  return (
    <div className="graph-node more">
      <Handles />
      <button type="button" className="graph-more-button nodrag nopan" onClick={data.onOpen}>
        {data.label}
      </button>
    </div>
  );
}

export const NODE_TYPES = {
  service: ServiceNodeView,
  target: TargetNodeView,
  more: MoreNodeView,
};
