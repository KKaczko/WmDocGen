import { Link } from "react-router";

import type { ServiceLink } from "../contract";
import { servicePath } from "./labels";

export function CallersSection({
  callers,
  total,
}: {
  callers: readonly ServiceLink[];
  total: number;
}) {
  return (
    <section className="section" aria-labelledby="callers-title">
      <h2 id="callers-title">Called by</h2>
      {callers.length === 0 ? (
        <p className="muted">
          No analysed service calls this one. It may be started by a trigger, a REST or SOAP
          endpoint, a scheduler, or from outside the analysed packages.
        </p>
      ) : (
        <>
          <ul className="link-list">
            {callers.map((caller) => (
              <li key={caller.id}>
                <Link to={servicePath(caller.name)} className="service-link">
                  {caller.name}
                </Link>
              </li>
            ))}
          </ul>
          {total > callers.length ? (
            <p className="note">
              Showing {callers.length} of {total} callers.
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
