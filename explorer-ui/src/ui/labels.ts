import type { Call, SearchService } from "../contract";

type Kind = SearchService["kind"];
type Analysis = SearchService["analysis"];
type CallStatus = Call["status"];

export const KIND_LABEL: Record<Kind, string> = {
  flow: "FLOW service",
  java: "Java service",
  adapter: "JDBC adapter service",
  opaque: "Other service type",
};

export const ANALYSIS_LABEL: Record<Analysis, string> = {
  full: "Fully analysed",
  partial: "Partly analysed",
  opaque: "Not analysed (opaque)",
};

export const STATUS_LABEL: Record<CallStatus, string> = {
  resolved: "In these packages",
  platform: "Built-in service",
  outside: "Outside the analysed packages",
  unresolved: "Unresolved",
  dynamic: "Decided at run time",
  unsupported: "Not interpreted",
};

export const STATUS_HELP: Record<CallStatus, string> = {
  resolved: "A service in the analysed packages; open it to read on.",
  platform: "A webMethods built-in service (pub.*, wm.*).",
  outside: "A service name that is not in the analysed packages.",
  unresolved: "The call target is not a valid service name.",
  dynamic: "The target is computed at run time, so the static analysis cannot follow it.",
  unsupported: "A call-like construct the analysis does not interpret.",
};

export const RELATION_LABEL: Record<Call["relation"], string> = {
  invokes: "invokes",
  transformer: "transformer",
  "java-invoke": "Java invoke",
  "call-like": "call-like step",
};

export function servicePath(name: string, packageName?: string): string {
  const query = packageName === undefined ? "" : `?package=${encodeURIComponent(packageName)}`;
  return `/s/${encodeURIComponent(name)}${query}`;
}

export function shortName(name: string): string {
  return name.slice(name.lastIndexOf(":") + 1);
}
