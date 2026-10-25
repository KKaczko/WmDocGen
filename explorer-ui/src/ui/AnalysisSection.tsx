import type { AnalysisInfo, SourceRef } from "../contract";
import { ANALYSIS_LABEL } from "./labels";

export function AnalysisSection({
  analysis,
  source,
}: {
  analysis: AnalysisInfo;
  source: SourceRef;
}) {
  return (
    <section className="section" aria-labelledby="analysis-title">
      <h2 id="analysis-title">Analysis coverage</h2>
      <dl className="facts">
        <dt>Status</dt>
        <dd>{ANALYSIS_LABEL[analysis.status]}</dd>
        <dt>Source file</dt>
        <dd>
          <code>{source.path}</code>
        </dd>
        <dt>Disabled steps</dt>
        <dd>
          {analysis.disabledSteps === 0
            ? "None"
            : `${String(analysis.disabledSteps)} (left out: they never run)`}
        </dd>
      </dl>
      {analysis.findings.length > 0 ? (
        <table className="table findings">
          <caption>What the analysis noticed</caption>
          <thead>
            <tr>
              <th scope="col">Severity</th>
              <th scope="col">Finding</th>
              <th scope="col" className="number">
                Count
              </th>
            </tr>
          </thead>
          <tbody>
            {analysis.findings.map((finding, index) => (
              <tr key={`${finding.code}-${String(index)}`}>
                <td>
                  <span className={`chip severity-${finding.severity}`}>{finding.severity}</span>
                </td>
                <td>
                  <code>{finding.code}</code>
                  <div>{finding.message}</div>
                  {finding.source !== null ? (
                    <div className="muted small">
                      <code>{finding.source.path}</code>
                    </div>
                  ) : null}
                </td>
                <td className="number">{finding.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted">No findings.</p>
      )}
      {analysis.findingsTotal > analysis.findings.length ? (
        <p className="note">
          Showing {analysis.findings.length} of {analysis.findingsTotal} findings.
        </p>
      ) : null}
    </section>
  );
}
