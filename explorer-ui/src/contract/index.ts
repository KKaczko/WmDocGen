// The data contract the app reads. Types are generated from the Python models (see
// scripts/gen-contract.mjs); only these constants are written by hand.
export type * from "./explorer-v1";

export const CONTRACT = "wm-doc-explorer.v1";

/** File IDs: 16 lowercase hex characters. Paths are only ever built from these. */
export const ID_PATTERN = /^[0-9a-f]{16}$/;
