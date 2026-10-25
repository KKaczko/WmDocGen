import type { Description, DescriptionSection as Section } from "../contract";
import { RichText } from "./RichText";
import { SectionHeading } from "./SectionHeading";

const TITLES: Record<Section["key"], string> = {
  purpose: "Purpose",
  usage: "Usage",
  dataEffects: "What it does to data",
  mainSteps: "Main steps",
  detailedFlow: "Detailed flow",
  errorHandling: "Error handling",
};

const WARNINGS: Partial<Record<Description["state"], string>> = {
  stale:
    "The facts of this service changed after the description was approved. Check it against the facts below.",
  draft: "Nobody has reviewed this description yet. Check it against the facts below.",
  edited: "This draft was edited by hand but not yet approved.",
};

/** "What it does": the purpose, usage and data narrative of a description file. */
export function DescriptionSection({
  description,
  descriptionsIncluded,
}: {
  description: Description | null;
  descriptionsIncluded: boolean;
}) {
  if (description === null) {
    return (
      <section className="section" aria-labelledby="description-title">
        <SectionHeading id="description-title" source="none">
          What it does
        </SectionHeading>
        <p className="muted">
          {descriptionsIncluded
            ? "No reviewed description for this service. The facts below come from static analysis."
            : "Descriptions are not included in this export. The facts below come from static analysis."}
        </p>
      </section>
    );
  }
  const sections = new Map(description.sections.map((section) => [section.key, section]));
  const warning = WARNINGS[description.state];
  return (
    <section className="section description" aria-labelledby="description-title">
      <SectionHeading id="description-title" source={description.state}>
        What it does
      </SectionHeading>
      {warning !== undefined ? (
        <p className="warning" role="note">
          {warning}
        </p>
      ) : null}
      {description.unverifiedNames.length > 0 ? (
        <p className="warning" role="note">
          The model used names that are not in the facts:{" "}
          {description.unverifiedNames.map((name, index) => (
            <span key={name}>
              {index > 0 ? ", " : ""}
              <code>{name}</code>
            </span>
          ))}
          . Check them before relying on this text.
        </p>
      ) : null}
      {(["purpose", "usage", "dataEffects"] as const).map((key) => (
        <SectionBody key={key} section={sections.get(key)} />
      ))}
      <p className="muted small">
        Written by <code>{description.model}</code>
        {description.detail !== null ? ` (detail: ${description.detail})` : ""}.
      </p>
    </section>
  );
}

/** Main steps, detailed flow and error handling, folded away by default. */
export function DescriptionDetails({ description }: { description: Description | null }) {
  if (description === null) return null;
  const sections = (["mainSteps", "detailedFlow", "errorHandling"] as const)
    .map((key) => description.sections.find((section) => section.key === key))
    .filter((section): section is Section => section !== undefined);
  if (sections.length === 0) return null;
  return (
    <section className="section" aria-labelledby="steps-title">
      <SectionHeading id="steps-title" source={description.state}>
        Steps in words
      </SectionHeading>
      {sections.map((section) => (
        <details key={section.key} open={section.key === "mainSteps"}>
          <summary>{TITLES[section.key]}</summary>
          <Blocks section={section} />
        </details>
      ))}
    </section>
  );
}

function SectionBody({ section }: { section: Section | undefined }) {
  if (section === undefined) return null;
  return (
    <div className="description-part">
      <h3>{TITLES[section.key]}</h3>
      <Blocks section={section} />
    </div>
  );
}

function Blocks({ section }: { section: Section }) {
  return (
    <>
      {section.paragraphs.map((paragraph, index) => (
        <p key={`p-${String(index)}`}>
          <RichText segments={paragraph} />
        </p>
      ))}
      {section.items.length > 0 ? (
        <ol>
          {section.items.map((item, index) => (
            <li key={`i-${String(index)}`}>
              <RichText segments={item} />
            </li>
          ))}
        </ol>
      ) : null}
    </>
  );
}
