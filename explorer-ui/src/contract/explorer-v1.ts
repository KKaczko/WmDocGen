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
  adapter: AdapterInfo | null;
  analysis: AnalysisInfo;
  callers: ServiceLink[];
  callersTotal: number;
  calls: Call[];
  callsTotal: number;
  contract: "wm-doc-explorer.v1";
  description: Description | null;
  documents: DocumentUse[];
  effects: Effect[];
  effectsHidden: number;
  entryPoints: EntryPoint[];
  entryPointsTotal: number;
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
 * Allow-listed JDBC adapter configuration (see wm_doc.adapters); never credentials.
 *
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "AdapterInfo".
 */
export interface AdapterInfo {
  adapterType: string | null;
  connection: string | null;
  databaseName: string | null;
  databaseProduct: string | null;
  operation: string | null;
  tables: string[];
  template: string | null;
  transactionType: string | null;
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
 * A reviewed or drafted description file: model-written, never a fact.
 *
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "Description".
 */
export interface Description {
  detail: string | null;
  model: string;
  sections: DescriptionSection[];
  state: "approved" | "stale" | "draft" | "edited";
  unverifiedNames: string[];
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "DescriptionSection".
 */
export interface DescriptionSection {
  items: (TextSegment | CodeSegment)[][];
  key:
    | "purpose"
    | "usage"
    | "dataEffects"
    | "mainSteps"
    | "detailedFlow"
    | "errorHandling"
    | "capabilities"
    | "areas"
    | "entryPoints"
    | "systemsAndData";
  paragraphs: (TextSegment | CodeSegment)[][];
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "TextSegment".
 */
export interface TextSegment {
  kind: "text";
  text: string;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "CodeSegment".
 */
export interface CodeSegment {
  code: string;
  kind: "code";
  ref: string | null;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "DocumentUse".
 */
export interface DocumentUse {
  name: string;
  resolved: boolean;
  role: "input" | "output" | "input-output";
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "Effect".
 */
export interface Effect {
  action: string;
  knownFrom: string;
  object: (TextSegment | CodeSegment)[];
  via: PathStep[];
  where: (TextSegment | CodeSegment)[];
}
/**
 * A service on a call chain; `id` is set when it is an analysed service.
 *
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "PathStep".
 */
export interface PathStep {
  id: string | null;
  name: string;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "EntryPoint".
 */
export interface EntryPoint {
  kind: string;
  name: (TextSegment | CodeSegment)[];
  path: PathStep[];
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
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "GraphData".
 */
export interface GraphData {
  contract: "wm-doc-explorer.v1";
  edges: [number, number, "invokes" | "transformer" | "java-invoke" | "call-like", number][];
  services: string[];
  targets: GraphTarget[];
}
/**
 * A call target that is not an analysed service.
 *
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "GraphTarget".
 */
export interface GraphTarget {
  name: string;
  note: string | null;
  status: "resolved" | "platform" | "outside" | "unresolved" | "dynamic" | "unsupported";
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "PackageDetail".
 */
export interface PackageDetail {
  calledFrom: PackageLink[];
  callsInto: PackageLink[];
  contract: "wm-doc-explorer.v1";
  documentTypes: number;
  effects: PackageEffect[];
  effectsTotal: number;
  entryPoints: PackageEntryPoint[];
  entryPointsTotal: number;
  id: string;
  name: string;
  overview: Description | null;
  services: PackageService[];
  servicesTotal: number;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "PackageLink".
 */
export interface PackageLink {
  calls: number;
  id: string | null;
  name: string;
}
/**
 * Data or a system the package's own services touch (not through other packages).
 *
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "PackageEffect".
 */
export interface PackageEffect {
  action: string;
  knownFrom: string[];
  object: (TextSegment | CodeSegment)[];
  services: PathStep[];
  servicesTotal: number;
  where: (TextSegment | CodeSegment)[];
}
/**
 * A service that work reaches from outside its package, and from where.
 *
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "PackageEntryPoint".
 */
export interface PackageEntryPoint {
  reachedFrom: (TextSegment | CodeSegment)[][];
  service: PathStep;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "PackageService".
 */
export interface PackageService {
  analysis: "full" | "partial" | "opaque";
  description: "approved" | "stale" | "draft" | "edited" | "none";
  id: string;
  kind: "flow" | "java" | "adapter" | "opaque";
  name: string;
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "ServerOverview".
 */
export interface ServerOverview {
  contract: "wm-doc-explorer.v1";
  description: Description | null;
  skippedPackages: SkippedPackage[];
}
/**
 * This interface was referenced by `ExplorerContractFiles`'s JSON-Schema
 * via the `definition` "SkippedPackage".
 */
export interface SkippedPackage {
  name: string;
  reason: string;
}
