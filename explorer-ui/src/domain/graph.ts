import type { GraphData, GraphTarget, SearchIndex, SearchService } from "../contract";

/**
 * The bounded neighbourhood of one service in the call graph Python emitted.
 *
 * Nothing here resolves names: edges come from graph.json as they are. The walk is a
 * breadth-first search from the focal service with the meaning of `--dependency-depth`
 * (depth 0 is the service alone, 1 adds its direct callers or callees, ...). It never shows
 * the whole server: a global node limit and a cap on new neighbours per node hold it, and
 * neighbours left out become one "+N more" node. Non-service targets (built-in, outside,
 * dynamic) are leaves. Output is deterministic: neighbours are visited in name order.
 */

export type Direction = "callees" | "callers" | "both";
export type Relation = GraphData["edges"][number][2];

export interface Neighbour {
  readonly node: number;
  readonly relation: Relation;
  readonly count: number;
}

export interface GraphIndex {
  readonly serviceCount: number;
  /** Search entry of each service node (index < serviceCount). */
  readonly services: readonly SearchService[];
  readonly targets: readonly GraphTarget[];
  /** Per node: what it calls / what calls it, sorted by name. */
  readonly outgoing: readonly (readonly Neighbour[])[];
  readonly incoming: readonly (readonly Neighbour[])[];
  nodeOf(id: string): number | undefined;
  name(node: number): string;
  isService(node: number): boolean;
  target(node: number): GraphTarget | undefined;
}

export interface WalkOptions {
  /** 0 = the service alone; Infinity = everything reachable (still capped). */
  readonly depth: number;
  readonly direction: Direction;
  /** Most nodes shown (not counting "+N more" nodes). */
  readonly maxNodes: number;
  /** Most new neighbours added per node and direction. */
  readonly maxPerNode: number;
  /** Show built-in (pub.*, wm.*) services. */
  readonly platform: boolean;
  /** Nodes opened one level beyond the depth. */
  readonly expanded?: ReadonlySet<number>;
}

export type Side = "focal" | "caller" | "callee";

export type ModelNode =
  | {
      readonly key: string;
      readonly type: "node";
      readonly node: number;
      readonly depth: number;
      readonly side: Side;
      /** A service whose further neighbours can be opened or closed. */
      readonly expandable: boolean;
      readonly expanded: boolean;
    }
  | {
      readonly key: string;
      readonly type: "more";
      readonly owner: number;
      readonly side: "caller" | "callee";
      readonly hidden: number;
    };

export interface ModelEdge {
  readonly key: string;
  readonly source: string;
  readonly target: string;
  readonly relation: Relation | "more";
  readonly count: number;
  /**
   * The edge that brought its node into the graph (a spanning tree). The layout uses only
   * these: cross edges are drawn too, but laying them out costs ten times as much.
   */
  readonly tree: boolean;
}

export interface GraphModel {
  readonly nodes: readonly ModelNode[];
  readonly edges: readonly ModelEdge[];
  /** True when the node limit stopped the walk: some neighbours are not shown. */
  readonly limitReached: boolean;
}

export const nodeKey = (node: number): string => `n${String(node)}`;
const moreKey = (owner: number, side: string): string => `more-${side}-${String(owner)}`;

export function indexGraph(graph: GraphData, search: SearchIndex): GraphIndex {
  const byId = new Map(search.services.map((service) => [service.id, service]));
  const services = graph.services.map((id) => {
    const service = byId.get(id);
    if (service === undefined) throw new Error(`graph.json names an unknown service ${id}`);
    return service;
  });
  const serviceCount = services.length;
  const size = serviceCount + graph.targets.length;
  const name = (node: number): string =>
    node < serviceCount
      ? (services[node]?.name ?? "")
      : (graph.targets[node - serviceCount]?.name ?? "");
  const outgoing: Neighbour[][] = Array.from({ length: size }, () => []);
  const incoming: Neighbour[][] = Array.from({ length: size }, () => []);
  for (const [source, target, relation, count] of graph.edges) {
    outgoing[source]?.push({ node: target, relation, count });
    incoming[target]?.push({ node: source, relation, count });
  }
  const order = (a: Neighbour, b: Neighbour): number =>
    compareNames(name(a.node), name(b.node)) || a.node - b.node;
  for (const list of outgoing) list.sort(order);
  for (const list of incoming) list.sort(order);
  const nodes = new Map(graph.services.map((id, index) => [id, index]));
  return {
    serviceCount,
    services,
    targets: graph.targets,
    outgoing,
    incoming,
    nodeOf: (id) => nodes.get(id),
    name,
    isService: (node) => node < serviceCount,
    target: (node) => (node < serviceCount ? undefined : graph.targets[node - serviceCount]),
  };
}

export function compareNames(a: string, b: string): number {
  const folded = a.toLowerCase().localeCompare(b.toLowerCase(), "en");
  if (folded !== 0) return folded;
  return a < b ? -1 : a > b ? 1 : 0;
}

/** Neighbours in one direction, without built-ins unless asked for. */
export function neighbours(
  index: GraphIndex,
  node: number,
  direction: "callers" | "callees",
  platform: boolean,
): readonly Neighbour[] {
  const list = direction === "callees" ? index.outgoing[node] : index.incoming[node];
  if (list === undefined) return [];
  return platform ? list : list.filter((item) => index.target(item.node)?.status !== "platform");
}

export function buildNeighborhood(
  index: GraphIndex,
  focal: number,
  options: WalkOptions,
): GraphModel {
  const expanded = options.expanded ?? new Set<number>();
  const placed = new Map<number, { depth: number; side: Side }>([
    [focal, { depth: 0, side: "focal" }],
  ]);
  const order: number[] = [focal];
  const edges = new Map<string, ModelEdge>();
  const more: Extract<ModelNode, { type: "more" }>[] = [];
  let limitReached = false;
  const queue: number[] = [focal];

  for (let head = 0; head < queue.length; head += 1) {
    const node = queue[head] as number;
    const info = placed.get(node);
    if (info === undefined || !index.isService(node)) continue;
    if (!(info.depth < options.depth || expanded.has(node))) continue;
    for (const direction of directionsFrom(info.side, options.direction)) {
      const side = direction === "callees" ? "callee" : "caller";
      let added = 0;
      let hidden = 0;
      for (const neighbour of neighbours(index, node, direction, options.platform)) {
        const isNew = !placed.has(neighbour.node);
        if (isNew) {
          if (placed.size >= options.maxNodes) {
            // The limit ends the walk; the panel says so instead of adding "+N more" nodes.
            limitReached = true;
            continue;
          }
          if (added >= options.maxPerNode) {
            hidden += 1;
            continue;
          }
          placed.set(neighbour.node, { depth: info.depth + 1, side });
          order.push(neighbour.node);
          queue.push(neighbour.node);
          added += 1;
        }
        const [from, to] =
          direction === "callees" ? [node, neighbour.node] : [neighbour.node, node];
        const key = `${nodeKey(from)}>${nodeKey(to)}:${neighbour.relation}`;
        if (!edges.has(key)) {
          edges.set(key, {
            key,
            source: nodeKey(from),
            target: nodeKey(to),
            relation: neighbour.relation,
            count: neighbour.count,
            tree: isNew,
          });
        }
      }
      if (hidden > 0) {
        const key = moreKey(node, side);
        more.push({ key, type: "more", owner: node, side, hidden });
        const [source, target] = side === "callee" ? [nodeKey(node), key] : [key, nodeKey(node)];
        edges.set(`${source}>${target}`, {
          key: `${source}>${target}`,
          source,
          target,
          relation: "more",
          count: hidden,
          tree: true,
        });
      }
    }
  }

  const nodes: ModelNode[] = order.map((node) => {
    const info = placed.get(node) as { depth: number; side: Side };
    const service = index.isService(node);
    const beyond = info.depth >= options.depth;
    return {
      key: nodeKey(node),
      type: "node",
      node,
      depth: info.depth,
      side: info.side,
      expandable:
        service && info.side !== "focal" && beyond && hasFurther(index, node, info.side, options),
      expanded: expanded.has(node),
    };
  });
  return { nodes: [...nodes, ...more], edges: [...edges.values()], limitReached };
}

function directionsFrom(side: Side, direction: Direction): ("callers" | "callees")[] {
  if (side === "caller") return ["callers"];
  if (side === "callee") return ["callees"];
  if (direction === "both") return ["callers", "callees"];
  return [direction];
}

function hasFurther(index: GraphIndex, node: number, side: Side, options: WalkOptions): boolean {
  return (
    neighbours(index, node, side === "caller" ? "callers" : "callees", options.platform).length > 0
  );
}

/** The services a model shows (focal included), by name: what the CLI scope would list. */
export function serviceNames(index: GraphIndex, model: GraphModel): string[] {
  return model.nodes
    .filter((node): node is Extract<ModelNode, { type: "node" }> => node.type === "node")
    .filter((node) => index.isService(node.node))
    .map((node) => index.name(node.node))
    .sort();
}
