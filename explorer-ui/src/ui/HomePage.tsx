import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";

import type { SearchPackage, SearchService } from "../contract";
import { useExplorer } from "../data/explorer-context";
import { useResource } from "../data/use-resource";
import { compareNames } from "../domain/graph";
import { DESCRIPTION_LABEL, OVERVIEW_LABEL, packagePath } from "./labels";
import { OverviewSection } from "./OverviewSection";
import { SectionHeading } from "./SectionHeading";

type SortKey = "name" | "services";

export function HomePage() {
  const { manifest, search, repository } = useExplorer();
  const overview = useResource(() => repository.overview(), "overview");
  const counts = manifest.counts;
  const coverage = useMemo(() => tally(search.services), [search.services]);

  useEffect(() => {
    document.title = "WmDocGen Explorer";
  }, []);

  return (
    <section className="home" aria-labelledby="home-title">
      <h1 id="home-title" tabIndex={-1}>
        Integration Server overview
      </h1>
      <p className="lead">
        Search for a service or package above (press <kbd>/</kbd>), or open a package below.
      </p>
      <dl className="counts">
        <div>
          <dt>Packages</dt>
          <dd>{counts.packages}</dd>
        </div>
        <div>
          <dt>Services</dt>
          <dd>{counts.services}</dd>
        </div>
        <div>
          <dt>Document types</dt>
          <dd>{counts.documentTypes}</dd>
        </div>
        <div>
          <dt>Calls</dt>
          <dd>{counts.calls}</dd>
        </div>
      </dl>
      {overview.status === "ready" ? (
        <OverviewSection
          id="server-overview-title"
          description={overview.data.description}
          missing="No reviewed server overview. Run `wm-doc overview --server` and approve it to show one here."
        />
      ) : null}
      <section className="section" aria-labelledby="coverage-title">
        <SectionHeading id="coverage-title" source="analysis">
          Coverage
        </SectionHeading>
        <div className="coverage-grid">
          <div>
            <h3>Analysis</h3>
            <ul className="plain-list">
              <li>
                <strong>{coverage.analysis.full}</strong> fully analysed
              </li>
              <li>
                <strong>{coverage.analysis.partial}</strong> partly analysed
              </li>
              <li>
                <strong>{coverage.analysis.opaque}</strong> not analysed (adapter and other
                services)
              </li>
            </ul>
          </div>
          <div>
            <h3>Descriptions</h3>
            <ul className="plain-list">
              {(Object.keys(DESCRIPTION_LABEL) as SearchService["description"][]).map((state) => (
                <li key={state}>
                  <strong>{coverage.descriptions[state]}</strong>{" "}
                  {DESCRIPTION_LABEL[state].toLowerCase()}
                </li>
              ))}
            </ul>
            {manifest.disclosure.descriptions === "approved" ? (
              <p className="note">Drafts are not included in this export.</p>
            ) : null}
          </div>
        </div>
      </section>
      <PackagesTable packages={search.packages} />
      {overview.status === "ready" && overview.data.skippedPackages.length > 0 ? (
        <section className="section" aria-labelledby="skipped-title">
          <SectionHeading id="skipped-title" source="analysis">
            Packages left out of the analysis
          </SectionHeading>
          <ul className="plain-list">
            {overview.data.skippedPackages.map((item) => (
              <li key={item.name}>
                <code>{item.name}</code> <span className="muted">— {item.reason}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <p className="muted small">
        Data contract {manifest.contract} · made by {manifest.generator.tool}{" "}
        {manifest.generator.version} from {manifest.generator.analysisSchema}
      </p>
    </section>
  );
}

function PackagesTable({ packages }: { packages: readonly SearchPackage[] }) {
  const [sort, setSort] = useState<SortKey>("name");
  const sorted = useMemo(
    () =>
      [...packages].sort((a, b) =>
        sort === "name"
          ? compareNames(a.name, b.name)
          : b.services - a.services || compareNames(a.name, b.name),
      ),
    [packages, sort],
  );
  const header = (key: SortKey, label: string, className?: string) => (
    <th
      scope="col"
      className={className}
      aria-sort={sort === key ? (key === "name" ? "ascending" : "descending") : "none"}
    >
      <button type="button" className="sort-button" onClick={() => setSort(key)}>
        {label}
      </button>
    </th>
  );
  return (
    <section className="section" aria-labelledby="packages-title">
      <SectionHeading id="packages-title" source="analysis">
        Packages
      </SectionHeading>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              {header("name", "Package")}
              {header("services", "Services", "number")}
              <th scope="col">Overview</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((item) => (
              <tr key={item.id}>
                <td>
                  <Link to={packagePath(item.name)}>{item.name}</Link>
                </td>
                <td className="number">{item.services}</td>
                <td>
                  {item.purpose ?? <span className="muted">{OVERVIEW_LABEL[item.overview]}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function tally(services: readonly SearchService[]) {
  const analysis = { full: 0, partial: 0, opaque: 0 };
  const descriptions = { approved: 0, stale: 0, draft: 0, edited: 0, none: 0 };
  for (const service of services) {
    analysis[service.analysis] += 1;
    descriptions[service.description] += 1;
  }
  return { analysis, descriptions };
}
