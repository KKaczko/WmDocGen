import type { Description } from "../contract";
import { Blocks, TITLES, WARNINGS } from "./DescriptionSection";
import { SectionHeading } from "./SectionHeading";

/** A package or server overview file, with its review state, or a note that there is none. */
export function OverviewSection({
  description,
  id,
  missing,
}: {
  description: Description | null;
  id: string;
  missing: string;
}) {
  const warning = description === null ? undefined : WARNINGS[description.state];
  return (
    <section className="section description" aria-labelledby={id}>
      <SectionHeading id={id} source={description?.state ?? "none"}>
        Overview
      </SectionHeading>
      {description === null ? <p className="muted">{missing}</p> : null}
      {warning !== undefined ? (
        <p className="warning" role="note">
          {warning}
        </p>
      ) : null}
      {description?.sections.map((section) => (
        <div key={section.key} className="description-part">
          <h3>{TITLES[section.key]}</h3>
          <Blocks section={section} />
        </div>
      ))}
      {description !== null ? (
        <p className="muted small">
          Written by <code>{description.model}</code>.
        </p>
      ) : null}
    </section>
  );
}
