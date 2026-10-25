import { Link } from "react-router";

import type { Call } from "../contract";
import { RELATION_LABEL, STATUS_HELP, STATUS_LABEL, servicePath } from "./labels";
import { SectionHeading } from "./SectionHeading";

export function CallsSection({ calls, total }: { calls: readonly Call[]; total: number }) {
  return (
    <section className="section" aria-labelledby="calls-title">
      <SectionHeading id="calls-title" source="analysis">
        Calls
      </SectionHeading>
      {calls.length === 0 ? (
        <p className="muted">This service calls no other service.</p>
      ) : (
        <>
          <p className="note">In the order of the first call. Open a service to read on.</p>
          <div className="table-wrap">
            <table className="table calls">
              <thead>
                <tr>
                  <th scope="col">Service</th>
                  <th scope="col">Status</th>
                  <th scope="col">How</th>
                  <th scope="col" className="number">
                    Calls
                  </th>
                  <th scope="col">Where</th>
                </tr>
              </thead>
              <tbody>
                {calls.map((call, index) => (
                  <CallRow key={`${call.target}-${call.relation}-${String(index)}`} call={call} />
                ))}
              </tbody>
            </table>
          </div>
          {total > calls.length ? (
            <p className="note">
              Showing {calls.length} of {total} calls.
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}

function CallRow({ call }: { call: Call }) {
  return (
    <tr>
      <td>
        {call.status === "resolved" && call.targetId !== null ? (
          <Link to={servicePath(call.target)} className="service-link">
            {call.target}
          </Link>
        ) : (
          <code>{call.target}</code>
        )}
        {call.note !== null ? <div className="muted small">{call.note}</div> : null}
      </td>
      <td>
        <span className={`chip status-${call.status}`} title={STATUS_HELP[call.status]}>
          {STATUS_LABEL[call.status]}
        </span>
        {call.status === "resolved" && call.targetAnalysis === "opaque" ? (
          <div className="muted small">not analysed (opaque)</div>
        ) : null}
      </td>
      <td>{RELATION_LABEL[call.relation]}</td>
      <td className="number">{call.count}</td>
      <td>
        {call.evidence.length > 0 ? (
          <details>
            <summary>Source</summary>
            <ul className="evidence">
              {call.evidence.map((item, index) => (
                <li key={`${item.path}-${String(index)}`}>
                  <code>{item.path}</code>
                  {item.xmlPath !== null ? (
                    <>
                      {" "}
                      <code className="muted">{item.xmlPath}</code>
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          </details>
        ) : (
          <span className="muted">—</span>
        )}
      </td>
    </tr>
  );
}
