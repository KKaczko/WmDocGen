import { useEffect } from "react";

import { useExplorer } from "../data/explorer-context";

export function HomePage() {
  const { manifest, search } = useExplorer();
  const counts = manifest.counts;
  const analysis = { full: 0, partial: 0, opaque: 0 };
  for (const service of search.services) analysis[service.analysis] += 1;

  useEffect(() => {
    document.title = "WmDocGen Explorer";
  }, []);

  return (
    <section className="home" aria-labelledby="home-title">
      <h1 id="home-title" tabIndex={-1}>
        Integration Server overview
      </h1>
      <p className="lead">
        Search for a service or package above (press <kbd>/</kbd>), then follow its calls and
        callers.
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
      <h2>Analysis coverage</h2>
      <ul className="coverage">
        <li>
          <strong>{analysis.full}</strong> fully analysed
        </li>
        <li>
          <strong>{analysis.partial}</strong> partly analysed
        </li>
        <li>
          <strong>{analysis.opaque}</strong> not analysed (opaque, for example adapter services)
        </li>
      </ul>
      <h2>Packages</h2>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Package</th>
              <th scope="col" className="number">
                Services
              </th>
            </tr>
          </thead>
          <tbody>
            {search.packages.map((item) => (
              <tr key={item.id}>
                <td>{item.name}</td>
                <td className="number">{item.services}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Data contract {manifest.contract} · made by {manifest.generator.tool}{" "}
        {manifest.generator.version} from {manifest.generator.analysisSchema}
      </p>
    </section>
  );
}
