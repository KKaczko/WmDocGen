import type { AdapterInfo, DocumentUse, Effect, EntryPoint } from "../contract";
import { PathChain, RichText } from "./RichText";
import { SectionHeading } from "./SectionHeading";

export function EntryPointsSection({
  entryPoints,
  total,
  hasCallers,
}: {
  entryPoints: readonly EntryPoint[];
  total: number;
  hasCallers: boolean;
}) {
  return (
    <section className="section" aria-labelledby="entry-title">
      <SectionHeading id="entry-title" source="analysis">
        Entry points
      </SectionHeading>
      {entryPoints.length === 0 ? (
        <p className="muted">
          {hasCallers
            ? "No entry point was found within the depth limit."
            : "Nothing in the analysed packages starts this service. It may be started from outside them (over HTTP, by a scheduler, or by a trigger in a package that was not analysed)."}
        </p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Entry point</th>
                <th scope="col">Kind</th>
                <th scope="col">Path to this service</th>
              </tr>
            </thead>
            <tbody>
              {entryPoints.map((entry, index) => (
                <tr key={`${entry.kind}-${String(index)}`}>
                  <td>
                    <RichText segments={entry.name} />
                  </td>
                  <td>{entry.kind}</td>
                  <td>
                    <PathChain steps={entry.path} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {total > entryPoints.length ? (
        <p className="note">
          Showing {entryPoints.length} of {total} entry points.
        </p>
      ) : null}
    </section>
  );
}

export function EffectsSection({
  effects,
  hidden,
}: {
  effects: readonly Effect[];
  hidden: number;
}) {
  return (
    <section className="section" aria-labelledby="effects-title">
      <SectionHeading id="effects-title" source="analysis">
        Data and systems touched
      </SectionHeading>
      {effects.length === 0 ? (
        <p className="muted">No data objects or external systems were found for this service.</p>
      ) : (
        <>
          <p className="note">
            By this service itself or through services it calls. Every row says how it is known.
          </p>
          <div className="table-wrap">
            <table className="table effects">
              <thead>
                <tr>
                  <th scope="col">Action</th>
                  <th scope="col">Object</th>
                  <th scope="col">Where</th>
                  <th scope="col">Via</th>
                  <th scope="col">Known from</th>
                </tr>
              </thead>
              <tbody>
                {effects.map((effect, index) => (
                  <tr key={`${effect.action}-${String(index)}`}>
                    <td>{effect.action}</td>
                    <td>
                      <RichText segments={effect.object} />
                    </td>
                    <td>
                      <RichText segments={effect.where} />
                    </td>
                    <td>
                      {effect.via.length === 0 ? (
                        <span className="muted">this service</span>
                      ) : (
                        <PathChain steps={effect.via} />
                      )}
                    </td>
                    <td className="muted">{effect.knownFrom}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {hidden > 0 ? <p className="note">And {hidden} more not shown.</p> : null}
    </section>
  );
}

const ROLE: Record<DocumentUse["role"], string> = {
  input: "input",
  output: "output",
  "input-output": "input and output",
};

export function DocumentsSection({ documents }: { documents: readonly DocumentUse[] }) {
  if (documents.length === 0) return null;
  return (
    <section className="section" aria-labelledby="documents-title">
      <SectionHeading id="documents-title" source="analysis">
        Document types used
      </SectionHeading>
      <ul className="link-list">
        {documents.map((document) => (
          <li key={`${document.name}-${document.role}`}>
            <code>{document.name}</code> <span className="muted">({ROLE[document.role]})</span>
            {document.resolved ? null : (
              <span className="chip status-unresolved"> not found in the packages</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function AdapterSection({ adapter }: { adapter: AdapterInfo | null }) {
  if (adapter === null) return null;
  const rows: [string, string | null][] = [
    ["Operation", adapter.operation],
    ["Tables", adapter.tables.length > 0 ? adapter.tables.join(", ") : null],
    ["Connection", adapter.connection],
    ["Database product", adapter.databaseProduct],
    ["Database name", adapter.databaseName],
    ["Transaction type", adapter.transactionType],
    ["Adapter", adapter.adapterType],
    ["Template", adapter.template],
  ];
  return (
    <section className="section" aria-labelledby="adapter-title">
      <SectionHeading id="adapter-title" source="adapter">
        Adapter configuration
      </SectionHeading>
      <dl className="facts">
        {rows
          .filter((row): row is [string, string] => row[1] !== null)
          .map(([label, value]) => (
            <div key={label} className="fact-row">
              <dt>{label}</dt>
              <dd>
                <code>{value}</code>
              </dd>
            </div>
          ))}
      </dl>
      <p className="note">
        Read from the adapter service&apos;s configuration. Credentials, hosts and SQL text are
        never read.
      </p>
    </section>
  );
}
