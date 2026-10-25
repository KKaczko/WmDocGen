import type { AnalysisInfo } from "../contract";

const TEXT: Record<AnalysisInfo["status"], string> = {
  full: "From static analysis of the package files.",
  partial: "From static analysis; parts of this service could not be analysed (see Analysis coverage).",
  opaque:
    "Not analysed: this service type is opaque to the tool. Only its identity, signature and callers are known.",
};

/** Says where the facts on a page come from, so nobody mistakes a gap for a fact. */
export function Provenance({ analysis }: { analysis: AnalysisInfo["status"] }) {
  return (
    <p className={`provenance provenance-${analysis}`}>
      <span className="provenance-label">Source of these facts:</span> {TEXT[analysis]}
    </p>
  );
}
