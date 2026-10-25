import { Graph, layout } from "@dagrejs/dagre";

import type { GraphModel } from "./graph";

export interface Box {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export const NODE_HEIGHT = 48;
const CHAR_WIDTH = 7.4;

export function nodeWidth(label: string): number {
  return Math.round(Math.min(340, Math.max(130, 40 + label.length * CHAR_WIDTH)));
}

/**
 * Left-to-right layered layout: callers to the left of the focal service, callees to the
 * right, placed along the spanning tree of the walk. Deterministic for the same model.
 */
export function layoutModel(
  model: GraphModel,
  label: (key: string) => string,
): ReadonlyMap<string, Box> {
  const graph = new Graph();
  graph.setGraph({ rankdir: "LR", nodesep: 14, ranksep: 70, marginx: 8, marginy: 8 });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const node of model.nodes) {
    graph.setNode(node.key, { width: nodeWidth(label(node.key)), height: NODE_HEIGHT });
  }
  for (const edge of model.edges) {
    if (edge.tree) graph.setEdge(edge.source, edge.target);
  }
  layout(graph);
  const boxes = new Map<string, Box>();
  for (const node of model.nodes) {
    const placed = graph.node(node.key);
    // dagre gives centres; React Flow wants top-left corners.
    boxes.set(node.key, {
      x: Math.round(placed.x - placed.width / 2),
      y: Math.round(placed.y - placed.height / 2),
      width: placed.width,
      height: placed.height,
    });
  }
  return boxes;
}
