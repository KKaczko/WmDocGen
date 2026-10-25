import type { Direction } from "../../domain/graph";

/** Graph settings live in the URL, so Back restores them and a link can be shared. */
export interface GraphSettings {
  readonly depth: number;
  readonly direction: Direction;
  readonly builtins: boolean;
  readonly limit: number;
  readonly view: "graph" | "list";
}

export const DEPTHS = [1, 2, 3, 4] as const;
export const LIMITS = [50, 150, 300] as const;
export const MAX_PER_NODE = 25;
export const DEFAULTS: GraphSettings = {
  depth: 2,
  direction: "both",
  builtins: false,
  limit: 150,
  view: "graph",
};

export function readSettings(params: URLSearchParams): GraphSettings {
  const depth = Number(params.get("depth"));
  const limit = Number(params.get("limit"));
  const direction = params.get("dir");
  return {
    depth: (DEPTHS as readonly number[]).includes(depth) ? depth : DEFAULTS.depth,
    direction:
      direction === "callers" || direction === "callees" || direction === "both"
        ? direction
        : DEFAULTS.direction,
    builtins: params.get("builtins") === "1",
    limit: (LIMITS as readonly number[]).includes(limit) ? limit : DEFAULTS.limit,
    view: params.get("view") === "list" ? "list" : "graph",
  };
}

/** Query parameters for settings that differ from the defaults (keeps URLs short). */
export function settingsQuery(settings: GraphSettings, base?: URLSearchParams): URLSearchParams {
  const query = new URLSearchParams(base);
  for (const key of ["depth", "dir", "builtins", "limit", "view"]) query.delete(key);
  if (settings.depth !== DEFAULTS.depth) query.set("depth", String(settings.depth));
  if (settings.direction !== DEFAULTS.direction) query.set("dir", settings.direction);
  if (settings.builtins) query.set("builtins", "1");
  if (settings.limit !== DEFAULTS.limit) query.set("limit", String(settings.limit));
  if (settings.view !== DEFAULTS.view) query.set("view", settings.view);
  return query;
}

/** A service page link that keeps the current graph settings. */
export function serviceGraphPath(name: string, settings: GraphSettings): string {
  const query = settingsQuery(settings).toString();
  return `/s/${encodeURIComponent(name)}${query === "" ? "" : `?${query}`}`;
}
