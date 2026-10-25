import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router";

import type { PackageDetail, PackageLink, PackageService, SearchPackage } from "../contract";
import { useExplorer } from "../data/explorer-context";
import { NotFoundError } from "../data/repository";
import { useResource } from "../data/use-resource";
import {
  ANALYSIS_LABEL,
  DESCRIPTION_LABEL,
  KIND_LABEL,
  OVERVIEW_LABEL,
  packagePath,
  servicePath,
} from "./labels";
import { OverviewSection } from "./OverviewSection";
import { PathChain, RichText } from "./RichText";
import { SectionHeading } from "./SectionHeading";

export function PackagePage() {
  const { name = "" } = useParams();
  const { packagesByName } = useExplorer();
  const entry = packagesByName.get(name);
  if (entry === undefined) return <PackageNotInExport name={name} />;
  return <PackageView key={entry.id} entry={entry} />;
}

function PackageView({ entry }: { entry: SearchPackage }) {
  const { repository } = useExplorer();
  const resource = useResource(() => repository.package(entry.id), entry.id);
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
    if (resource.error instanceof NotFoundError) return <PackageNotInExport name={entry.name} />;
    return (
      <p className="status-line error" role="alert">
        {resource.error.message}
      </p>
    );
  }
  const detail = resource.data;
  return (
    <article className="service" aria-labelledby="package-title">
      <header className="service-header">
        <p className="eyebrow">Package</p>
        <h1 id="package-title" ref={heading} tabIndex={-1}>
          {detail.name}
        </h1>
        <ul className="badges" aria-label="Package facts">
          <li className="badge">{detail.servicesTotal} services</li>
          <li className="badge">{detail.documentTypes} document types</li>
          <li className="badge">{detail.entryPointsTotal} entry points</li>
          <li className={`badge description-${entry.overview}`}>
            {OVERVIEW_LABEL[entry.overview]}
          </li>
        </ul>
      </header>
      <OverviewSection
        id="package-overview-title"
        description={detail.overview}
        missing="No reviewed overview for this package. The facts below come from static analysis."
      />
      <ServicesSection services={detail.services} total={detail.servicesTotal} />
      <EntrySection detail={detail} />
      <NeighboursSection detail={detail} />
      <PackageEffectsSection detail={detail} />
    </article>
  );
}

function ServicesSection({
  services,
  total,
}: {
  services: readonly PackageService[];
  total: number;
}) {
  const id = useId();
  const [text, setText] = useState("");
  const [kind, setKind] = useState<PackageService["kind"] | "">("");
  const shown = useMemo(() => {
    const needle = text.trim().toLowerCase();
    return services.filter(
      (service) =>
        (needle === "" || service.name.toLowerCase().includes(needle)) &&
        (kind === "" || service.kind === kind),
    );
  }, [services, text, kind]);
  return (
    <section className="section" aria-labelledby="package-services-title">
      <SectionHeading id="package-services-title" source="analysis">
        Services
      </SectionHeading>
      <div className="graph-controls">
        <label htmlFor={`${id}-filter`}>
          Filter{" "}
          <input
            id={`${id}-filter`}
            type="search"
            value={text}
            placeholder="part of a name"
            onChange={(event) => setText(event.target.value)}
          />
        </label>
        <label htmlFor={`${id}-kind`}>
          Type{" "}
          <select
            id={`${id}-kind`}
            value={kind}
            onChange={(event) => setKind(event.target.value as PackageService["kind"] | "")}
          >
            <option value="">all</option>
            {(Object.keys(KIND_LABEL) as PackageService["kind"][]).map((key) => (
              <option key={key} value={key}>
                {KIND_LABEL[key]}
              </option>
            ))}
          </select>
        </label>
        <span className="note" role="status">
          {shown.length} of {total} shown
        </span>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Service</th>
              <th scope="col">Type</th>
              <th scope="col">Analysis</th>
              <th scope="col">Description</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((service) => (
              <tr key={service.id}>
                <td>
                  <Link to={servicePath(service.name)} className="service-link">
                    {service.name}
                  </Link>
                </td>
                <td>{KIND_LABEL[service.kind]}</td>
                <td>{ANALYSIS_LABEL[service.analysis]}</td>
                <td>{DESCRIPTION_LABEL[service.description]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EntrySection({ detail }: { detail: PackageDetail }) {
  return (
    <section className="section" aria-labelledby="package-entry-title">
      <SectionHeading id="package-entry-title" source="analysis">
        Entry points
      </SectionHeading>
      {detail.entryPoints.length === 0 ? (
        <p className="muted">Nothing outside this package reaches its services.</p>
      ) : (
        <>
          <p className="note">
            Services that work reaches from outside this package, and from where.
          </p>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Service</th>
                  <th scope="col">Reached from</th>
                </tr>
              </thead>
              <tbody>
                {detail.entryPoints.map((entry) => (
                  <tr key={entry.service.name}>
                    <td>
                      <PathChain steps={[entry.service]} />
                    </td>
                    <td>
                      <ul className="plain-list">
                        {entry.reachedFrom.map((segments, index) => (
                          <li key={String(index)}>
                            <RichText segments={segments} />
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {detail.entryPointsTotal > detail.entryPoints.length ? (
        <p className="note">
          Showing {detail.entryPoints.length} of {detail.entryPointsTotal}.
        </p>
      ) : null}
    </section>
  );
}

function NeighboursSection({ detail }: { detail: PackageDetail }) {
  return (
    <section className="section" aria-labelledby="package-neighbours-title">
      <SectionHeading id="package-neighbours-title" source="analysis">
        Other packages
      </SectionHeading>
      <div className="neighbours">
        <PackageLinks
          title="Calls into"
          links={detail.callsInto}
          empty="No other analysed package."
        />
        <PackageLinks
          title="Called from"
          links={detail.calledFrom}
          empty="No other analysed package."
        />
      </div>
      <p className="note">
        Counts are service-to-service dependencies crossing between the packages.
      </p>
    </section>
  );
}

function PackageLinks({
  title,
  links,
  empty,
}: {
  title: string;
  links: readonly PackageLink[];
  empty: string;
}) {
  return (
    <div>
      <h3>{title}</h3>
      {links.length === 0 ? <p className="muted">{empty}</p> : null}
      <ul className="plain-list">
        {links.map((link) => (
          <li key={link.name}>
            {link.id !== null ? <Link to={packagePath(link.name)}>{link.name}</Link> : link.name}{" "}
            <span className="muted">({link.calls})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PackageEffectsSection({ detail }: { detail: PackageDetail }) {
  return (
    <section className="section" aria-labelledby="package-effects-title">
      <SectionHeading id="package-effects-title" source="analysis">
        Data and systems touched
      </SectionHeading>
      {detail.effects.length === 0 ? (
        <p className="muted">The services of this package touch no data or systems themselves.</p>
      ) : (
        <>
          <p className="note">
            By this package&apos;s own services; data reached through other packages is listed
            there.
          </p>
          <div className="table-wrap">
            <table className="table effects">
              <thead>
                <tr>
                  <th scope="col">Action</th>
                  <th scope="col">Object</th>
                  <th scope="col">Where</th>
                  <th scope="col">Services</th>
                  <th scope="col">Known from</th>
                </tr>
              </thead>
              <tbody>
                {detail.effects.map((effect, index) => (
                  <tr key={`${effect.action}-${String(index)}`}>
                    <td>{effect.action}</td>
                    <td>
                      <RichText segments={effect.object} />
                    </td>
                    <td>
                      <RichText segments={effect.where} />
                    </td>
                    <td>
                      <ul className="plain-list">
                        {effect.services.map((service) => (
                          <li key={service.name}>
                            <PathChain steps={[service]} />
                          </li>
                        ))}
                      </ul>
                      {effect.servicesTotal > effect.services.length ? (
                        <span className="muted small">
                          and {effect.servicesTotal - effect.services.length} more
                        </span>
                      ) : null}
                    </td>
                    <td className="muted">{effect.knownFrom.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function PackageNotInExport({ name }: { name: string }) {
  useEffect(() => {
    document.title = "Not in this export · WmDocGen Explorer";
  }, []);
  return (
    <section className="message-page">
      <h1>Not in this export</h1>
      <p>
        The package <code>{name}</code> is not among the analysed packages in this explorer. It may
        have been skipped (see the overview) or the name may be misspelled.
      </p>
      <p>
        <Link to="/">Back to the overview</Link>
      </p>
    </section>
  );
}
