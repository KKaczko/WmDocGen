import { Suspense, lazy, useEffect, useRef } from "react";
import type { RefObject } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import type { SearchService, ServiceDetail } from "../contract";
import { useExplorer } from "../data/explorer-context";
import { NotFoundError } from "../data/repository";
import { useResource } from "../data/use-resource";
import { AnalysisSection } from "./AnalysisSection";
import { CallersSection } from "./CallersSection";
import { CallsSection } from "./CallsSection";
import { CopyButton } from "./CopyButton";
import { DescriptionDetails, DescriptionSection } from "./DescriptionSection";
import {
  AdapterSection,
  DocumentsSection,
  EffectsSection,
  EntryPointsSection,
} from "./FactsSections";
import { ANALYSIS_LABEL, DESCRIPTION_LABEL, KIND_LABEL, packagePath, servicePath } from "./labels";
import { Provenance } from "./Provenance";
import { SignatureSection } from "./SignatureSection";

// The graph code (React Flow, dagre) is loaded only when a service page opens.
const GraphPanel = lazy(() =>
  import("./graph/GraphPanel").then((module) => ({ default: module.GraphPanel })),
);

export function ServicePage() {
  const { name = "" } = useParams();
  const [params] = useSearchParams();
  const { servicesByName } = useExplorer();
  const wanted = params.get("package");
  const matches = servicesByName.get(name) ?? [];
  const entry = wanted === null ? matches[0] : matches.find((item) => item.package === wanted);

  if (matches.length === 0) {
    return <NotInExport name={name} />;
  }
  if (matches.length > 1 && entry !== undefined && wanted === null) {
    return <Chooser name={name} matches={matches} />;
  }
  if (entry === undefined) {
    return <NotInExport name={name} />;
  }
  return <ServiceView key={entry.id} entry={entry} />;
}

function ServiceView({ entry }: { entry: SearchService }) {
  const { repository } = useExplorer();
  const resource = useResource(() => repository.service(entry.id), entry.id);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    document.title = `${entry.name} · WmDocGen Explorer`;
  }, [entry.name]);
  useEffect(() => {
    if (resource.status === "ready") heading.current?.focus();
  }, [resource.status]);

  if (resource.status === "loading") {
    return (
      <p className="status-line" role="status">
        Loading {entry.name}…
      </p>
    );
  }
  if (resource.status === "error") {
    if (resource.error instanceof NotFoundError) return <NotInExport name={entry.name} />;
    return (
      <p className="status-line error" role="alert">
        {resource.error.message}
      </p>
    );
  }
  return <ServiceDetails detail={resource.data} heading={heading} />;
}

function ServiceDetails({
  detail,
  heading,
}: {
  detail: ServiceDetail;
  heading: RefObject<HTMLHeadingElement | null>;
}) {
  const { manifest } = useExplorer();
  const descriptionState = detail.description?.state ?? "none";
  return (
    <article className="service" aria-labelledby="service-title">
      <header className="service-header">
        <h1 id="service-title" ref={heading} tabIndex={-1}>
          {detail.shortName}
        </h1>
        <p className="full-name">
          <code>{detail.name}</code>
          <CopyButton text={detail.name} label="Copy the full service name" />
        </p>
        <ul className="badges" aria-label="Service facts">
          <li className="badge">
            Package <Link to={packagePath(detail.package.name)}>{detail.package.name}</Link>
          </li>
          <li className={`badge kind-${detail.kind}`}>{KIND_LABEL[detail.kind]}</li>
          <li className={`badge analysis-${detail.analysis.status}`}>
            {ANALYSIS_LABEL[detail.analysis.status]}
          </li>
          <li className={`badge description-${descriptionState}`}>
            {DESCRIPTION_LABEL[descriptionState]}
          </li>
        </ul>
        <Provenance analysis={detail.analysis.status} />
      </header>
      <DescriptionSection
        description={detail.description}
        descriptionsIncluded={manifest.disclosure.descriptions !== "none"}
      />
      <Suspense
        fallback={
          <p className="section muted" role="status">
            Loading the call graph…
          </p>
        }
      >
        <GraphPanel focalId={detail.id} focalName={detail.name} />
      </Suspense>
      <AdapterSection adapter={detail.adapter} />
      <SignatureSection signature={detail.signature} />
      <CallsSection calls={detail.calls} total={detail.callsTotal} />
      <CallersSection callers={detail.callers} total={detail.callersTotal} />
      <EntryPointsSection
        entryPoints={detail.entryPoints}
        total={detail.entryPointsTotal}
        hasCallers={detail.callersTotal > 0}
      />
      <EffectsSection effects={detail.effects} hidden={detail.effectsHidden} />
      <DocumentsSection documents={detail.documents} />
      <DescriptionDetails description={detail.description} />
      <AnalysisSection analysis={detail.analysis} source={detail.source} />
    </article>
  );
}

function NotInExport({ name }: { name: string }) {
  useEffect(() => {
    document.title = "Not in this export · WmDocGen Explorer";
  }, []);
  return (
    <section className="message-page">
      <h1>Not in this export</h1>
      <p>
        <code>{name}</code> is not among the analysed services in this explorer. It may live in a
        package that was not analysed, or the name may be misspelled.
      </p>
      <p>
        <Link to="/">Back to the overview</Link>
      </p>
    </section>
  );
}

function Chooser({ name, matches }: { name: string; matches: readonly SearchService[] }) {
  return (
    <section className="message-page">
      <h1>Several services share this name</h1>
      <p>
        <code>{name}</code> exists in more than one analysed package. Integration Server loads only
        one of them; choose the package:
      </p>
      <ul>
        {matches.map((match) => (
          <li key={match.id}>
            <Link to={servicePath(match.name, match.package)}>{match.package}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
