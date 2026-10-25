/* Generated from docs/contracts/explorer.v1.schema.json by scripts/gen-contract.mjs.
 * Do not edit: change wm_doc/explorer/contract.py, then regenerate both. */

export interface ExplorerContractFiles {
  manifest: Manifest;
  search: SearchIndex;
  service: ServiceDetail;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "Manifest".
 */
export interface Manifest {
  contract: "wm-doc-explorer.v1";
  counts: Counts;
  dataset: Dataset;
  digest: string;
  disclosure: Disclosure;
  generator: Generator;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "Counts".
 */
export interface Counts {
  approvedDescriptions: number;
  calls: number;
  documentTypes: number;
  packages: number;
  services: number;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "Dataset".
 */
export interface Dataset {
  kind: "synthetic" | "private";
  label: string;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "Disclosure".
 */
export interface Disclosure {
  descriptions: "approved" | "all" | "none";
  designerComments: "excluded";
  literals: "excluded";
  notes: "excluded";
  withheldStrings: number;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "Generator".
 */
export interface Generator {
  analysisSchema: string;
  tool: string;
  version: string;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "SearchIndex".
 */
export interface SearchIndex {
  contract: "wm-doc-explorer.v1";
  packages: SearchPackage[];
  services: SearchService[];
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "SearchPackage".
 */
export interface SearchPackage {
  id: string;
  name: string;
  overview: "approved" | "stale" | "draft" | "edited" | "none";
  purpose: string | null;
  services: number;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "SearchService".
 */
export interface SearchService {
  analysis: "full" | "partial" | "opaque";
  description: "approved" | "stale" | "draft" | "edited" | "none";
  id: string;
  kind: "flow" | "java" | "adapter" | "opaque";
  name: string;
  package: string;
  purpose: string | null;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "ServiceDetail".
 */
export interface ServiceDetail {
  analysis: AnalysisInfo;
  callers: ServiceLink[];
  callersTotal: number;
  calls: Call[];
  callsTotal: number;
  contract: "wm-doc-explorer.v1";
  id: string;
  kind: "flow" | "java" | "adapter" | "opaque";
  name: string;
  namespace: string;
  package: PackageRef;
  shortName: string;
  signature: Signature;
  source: SourceRef;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "AnalysisInfo".
 */
export interface AnalysisInfo {
  disabledSteps: number;
  findings: Finding[];
  findingsTotal: number;
  status: "full" | "partial" | "opaque";
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "Finding".
 */
export interface Finding {
  code: string;
  count: number;
  message: string;
  severity: "info" | "warning" | "error";
  source: SourceRef | null;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "SourceRef".
 */
export interface SourceRef {
  path: string;
  xmlPath: string | null;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "ServiceLink".
 */
export interface ServiceLink {
  id: string;
  name: string;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "Call".
 */
export interface Call {
  count: number;
  evidence: SourceRef[];
  firstOrder: number | null;
  note: string | null;
  relation: "invokes" | "transformer" | "java-invoke" | "call-like";
  status: "resolved" | "platform" | "outside" | "unresolved" | "dynamic" | "unsupported";
  target: string;
  targetAnalysis: ("full" | "partial" | "opaque") | null;
  targetId: string | null;
  targetKind: ("flow" | "java" | "adapter" | "opaque") | null;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "PackageRef".
 */
export interface PackageRef {
  id: string;
  name: string;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "Signature".
 */
export interface Signature {
  inputs: SignatureField[];
  origin: "service" | "specification";
  outputs: SignatureField[];
  specification: string | null;
  truncated: boolean;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "SignatureField".
 */
export interface SignatureField {
  children: SignatureField[];
  dimension: number;
  document: DocumentRef | null;
  name: string;
  optional: boolean | null;
  type: string | null;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "DocumentRef".
 */
export interface DocumentRef {
  name: string;
  resolved: boolean;
}
