import type { ReactNode } from "react";

export type SourceKind =
  "analysis" | "adapter" | "approved" | "stale" | "draft" | "edited" | "none";

const SOURCE_TEXT: Record<SourceKind, string> = {
  analysis: "From static analysis",
  adapter: "From the adapter configuration",
  approved: "AI-written, approved by a reviewer",
  stale: "AI-written and approved, but the facts changed since",
  draft: "AI draft, not reviewed",
  edited: "AI draft edited by hand, not reviewed",
  none: "No description",
};

/** A section heading with a label saying where the content comes from. */
export function SectionHeading({
  id,
  children,
  source,
}: {
  id: string;
  children: ReactNode;
  source: SourceKind;
}) {
  return (
    <div className="section-heading">
      <h2 id={id}>{children}</h2>
      <span className={`source source-${source}`}>{SOURCE_TEXT[source]}</span>
    </div>
  );
}
