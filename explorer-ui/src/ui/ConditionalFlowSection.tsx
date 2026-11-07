import { useState } from "react";
import { Link } from "react-router";

import type {
  FlowCall,
  FlowDecision,
  FlowField,
  FlowOrigin,
  FlowRef,
  FlowScenarioTable,
  FlowStep,
  FlowView,
  Manifest,
  Segment,
} from "../contract";
import { useExplorer } from "../data/explorer-context";
import { useResource } from "../data/use-resource";
import { servicePath } from "./labels";
import { RichText } from "./RichText";
import { SectionHeading } from "./SectionHeading";

type ConditionValues = Manifest["disclosure"]["conditionValues"];

/** Words in front of a step whose text does not already say what kind of step it is. */
const PREFIX: Partial<Record<FlowStep["kind"], string>> = {
  case: "when",
  call: "calls",
  transformer: "transformer",
  exit: "EXIT",
};

const BASIS: Record<FlowOrigin["basis"], string> = {
  "flow-xml": "from the FLOW",
  "is-rule": "IS rule",
  "callee-signature": "called service's signature",
  "service-signature": "this service's signature",
  "caller-pipeline": "caller's pipeline",
  limit: "not followed",
};

/**
 * When each step of a FLOW service runs: an outline, the decisions with their cases and the
 * origins of the fields they test, the calls by condition and the scenarios. Python prepared
 * every fact and every text; this only shows them. The file is loaded when the reader opens
 * the section.
 */
export function ConditionalFlowSection({
  serviceId,
  flow,
}: {
  serviceId: string;
  flow: FlowRef | null;
}) {
  const [open, setOpen] = useState(false);
  if (flow === null) return null;
  return (
    <section className="section" aria-labelledby="flow-title">
      <SectionHeading id="flow-title" source="analysis">
        Conditional flow
      </SectionHeading>
      <details
        className="flow"
        onToggle={(event) => {
          setOpen(event.currentTarget.open);
        }}
      >
        <summary>
          Show when each step runs ({plural(flow.decisions, "decision")},{" "}
          {plural(flow.calls, "call")}, {plural(flow.exits, "EXIT step")})
        </summary>
        {open ? <FlowLoader serviceId={serviceId} /> : null}
      </details>
    </section>
  );
}

function FlowLoader({ serviceId }: { serviceId: string }) {
  const { repository, manifest } = useExplorer();
  const resource = useResource(() => repository.flow(serviceId), serviceId);
  if (resource.status === "loading") {
    return (
      <p className="status-line" role="status">
        Loading the conditional flow…
      </p>
    );
  }
  if (resource.status === "error") {
    return (
      <p className="status-line error" role="alert">
        {resource.error.message}
      </p>
    );
  }
  return <FlowContent flow={resource.data} conditionValues={manifest.disclosure.conditionValues} />;
}

export function FlowContent({
  flow,
  conditionValues,
}: {
  flow: FlowView;
  conditionValues: ConditionValues;
}) {
  return (
    <div className="flow-content">
      <p className="note">
        Read from the FLOW structure; conditions are shown as written and never evaluated. D1, C1
        and E1 number the decisions (BRANCH steps), calls and EXIT steps in the order they appear.
        “derived” follows from the FLOW and the Integration Server rules; an “assumption” label
        names a rule not yet confirmed on IS 10.15.
      </p>
      {conditionValues === "excluded" ? (
        <p className="note">Condition values (case labels) are not included in this export.</p>
      ) : null}
      <h3>Outline</h3>
      <Outline steps={flow.outline} />
      <More count={flow.outlineHidden} noun="step" />
      {flow.decisions.map((decision) => (
        <DecisionCard key={decision.id} decision={decision} />
      ))}
      <More count={flow.decisionsHidden} noun="decision" />
      <Scenarios tables={flow.scenarios} notes={flow.scenarioNotes} />
      <CallsByCondition calls={flow.calls} hidden={flow.callsHidden} />
      <TextList title="Exits" items={flow.exits} hidden={flow.exitsHidden} noun="EXIT step" />
      <TextList
        title="Steps that never run"
        items={flow.neverRun}
        hidden={flow.neverRunHidden}
        noun="step"
      />
      <TextList title="Limits" items={flow.limits} hidden={0} noun="limit" />
    </div>
  );
}

// --- outline -----------------------------------------------------------------------------------

function Outline({ steps }: { steps: readonly FlowStep[] }) {
  if (steps.length === 0) return null;
  return (
    <ul className="flow-outline">
      {steps.map((step, index) => (
        <OutlineStep key={`${step.ref ?? step.kind}-${String(index)}`} step={step} />
      ))}
    </ul>
  );
}

function OutlineStep({ step }: { step: FlowStep }) {
  if (step.children.length === 0) {
    return (
      <li>
        <StepLabel step={step} links />
      </li>
    );
  }
  return (
    <li>
      <details>
        {/* A summary is itself the control, so it holds no links (see the line below it). */}
        <summary>
          <StepLabel step={step} links={false} />
        </summary>
        {step.targetId !== null && codeOf(step.text) !== "" ? (
          <p className="flow-open">
            <ServiceLink name={codeOf(step.text)} />
          </p>
        ) : null}
        <Outline steps={step.children} />
      </details>
    </li>
  );
}

function StepLabel({ step, links }: { step: FlowStep; links: boolean }) {
  const prefix = PREFIX[step.kind];
  return (
    <span className={`flow-step flow-step-${step.kind}`}>
      {step.ref !== null ? (
        <>
          <span className="flow-ref">{step.ref}</span>{" "}
        </>
      ) : null}
      {prefix !== undefined ? <span className="flow-kind">{prefix} </span> : null}
      <RichText segments={links ? step.text : unlinked(step.text)} />
      {step.never ? <span className="chip flow-never">never runs</span> : null}
    </span>
  );
}

// --- decisions ---------------------------------------------------------------------------------

function DecisionCard({ decision }: { decision: FlowDecision }) {
  const id = `flow-${decision.id}`;
  return (
    <section className="flow-decision" aria-labelledby={id}>
      <h3 id={id}>
        <span className="flow-ref">{decision.id}</span> <RichText segments={decision.heading} />
      </h3>
      {decision.evaluatedWhen !== null ? (
        <p>
          Evaluated only when: <RichText segments={decision.evaluatedWhen} />.
        </p>
      ) : null}
      {decision.inLoop ? (
        <p className="note">It is inside a loop, so each iteration may take a different case.</p>
      ) : null}
      {decision.notes.map((note, index) => (
        <p key={String(index)} className="note">
          <RichText segments={note} />
        </p>
      ))}
      <div className="table-wrap">
        <table className="table flow-cases">
          <caption className="visually-hidden">Cases of {decision.id}</caption>
          <thead>
            <tr>
              <th scope="col">Case</th>
              <th scope="col">Condition</th>
              <th scope="col">Calls, in order</th>
              <th scope="col">Ends with</th>
              <th scope="col">Notes</th>
            </tr>
          </thead>
          <tbody>
            {decision.cases.map((item) => (
              <tr key={item.id}>
                <th scope="row">
                  <span className="flow-ref">{item.id}</span>
                </th>
                <td>
                  <RichText segments={item.condition} />
                </td>
                <td>
                  <Cell segments={item.calls} />
                </td>
                <td>
                  <Cell segments={item.ends} />
                </td>
                <td>
                  {item.never ? <span className="chip flow-never">never runs</span> : null}{" "}
                  <RichText segments={item.notes} />
                </td>
              </tr>
            ))}
            {decision.noMatch !== null ? (
              <tr>
                <th scope="row">-</th>
                <td>no case matches</td>
                <td>-</td>
                <td>-</td>
                <td>
                  <RichText segments={decision.noMatch} />
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <More count={decision.casesHidden} noun="case" />
      {decision.unfollowed.map((note, index) => (
        <p key={String(index)} className="note">
          <RichText segments={note} />
        </p>
      ))}
      {decision.fields.map((field) => (
        <FieldOrigins key={field.path} field={field} />
      ))}
      <More count={decision.fieldsHidden} noun="field" />
    </section>
  );
}

function FieldOrigins({ field }: { field: FlowField }) {
  return (
    <div className="flow-field">
      <h4>
        Where <code>{field.path}</code> comes from
      </h4>
      <p>
        <RichText segments={field.summary} />
      </p>
      {field.origins.length > 0 ? (
        <ul className="flow-origins">
          {field.origins.map((origin, index) => (
            <li key={String(index)} className={`flow-depth-${String(Math.min(origin.depth, 5))}`}>
              {origin.copied !== null ? (
                <>
                  <code>{origin.copied}</code>:{" "}
                </>
              ) : null}
              <RichText segments={origin.text} /> <OriginChips origin={origin} />
            </li>
          ))}
        </ul>
      ) : null}
      <More count={field.originsHidden} noun="origin" />
      {field.notes.map((note, index) => (
        <p key={String(index)} className="note">
          <RichText segments={note} />
        </p>
      ))}
    </div>
  );
}

function OriginChips({ origin }: { origin: FlowOrigin }) {
  return (
    <span className="flow-chips">
      <span className={`chip certainty-${origin.certainty}`}>{origin.certainty}</span>{" "}
      <span className="chip">{BASIS[origin.basis]}</span>
      {origin.assumptions !== null ? (
        <>
          {" "}
          <span className="chip flow-assumption">{origin.assumptions}</span>
        </>
      ) : null}
      {origin.evidence !== null ? (
        <span className="muted">
          {" "}
          in <code>{origin.evidence.path}</code>
        </span>
      ) : null}
    </span>
  );
}

// --- scenarios, calls, lists -------------------------------------------------------------------

function Scenarios({
  tables,
  notes,
}: {
  tables: readonly FlowScenarioTable[];
  notes: readonly Segment[][];
}) {
  if (tables.length === 0 && notes.length === 0) return null;
  return (
    <section className="flow-part" aria-labelledby="flow-scenarios">
      <h3 id="flow-scenarios">Scenarios</h3>
      <p className="note">
        Decisions whose fields depend on an earlier decision are combined along that dependency;
        decisions that depend on no other one are never multiplied with each other. “possible”:
        values this service sets itself may lead there; “conditional”: it also needs a value from
        the caller or a call&apos;s response; “unresolved”: a field or condition is not followed.
      </p>
      {tables.map((table) => (
        <ScenarioTableView key={table.decisions.join("-")} table={table} />
      ))}
      {notes.map((note, index) => (
        <p key={String(index)} className="note">
          <RichText segments={note} />
        </p>
      ))}
    </section>
  );
}

function ScenarioTableView({ table }: { table: FlowScenarioTable }) {
  const name = table.decisions.join(", ");
  return (
    <div className="flow-scenarios">
      <h4>{name}</h4>
      {table.rows.length > 0 ? (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">Scenarios of {name}</caption>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Conditions</th>
                <th scope="col">Calls, in order</th>
                <th scope="col">Ends with</th>
                <th scope="col">Depends on responses of</th>
                <th scope="col">Feasibility</th>
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row) => (
                <tr key={row.id}>
                  <th scope="row">{row.id}</th>
                  <td>
                    <RichText segments={row.conditions} />
                  </td>
                  <td>
                    <Cell segments={row.calls} />
                  </td>
                  <td>
                    <Cell segments={row.ends} />
                  </td>
                  <td>
                    <Cell segments={row.dependsOn} />
                  </td>
                  <td>
                    <span className={`chip feasibility-${row.feasibility}`}>{row.feasibility}</span>
                    {row.assumptions !== null ? (
                      <span className="muted"> ({row.assumptions})</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {table.notes.length > 0 ? (
        <ul className="link-list">
          {table.notes.map((note, index) => (
            <li key={String(index)}>
              <RichText segments={note} />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function CallsByCondition({ calls, hidden }: { calls: readonly FlowCall[]; hidden: number }) {
  if (calls.length === 0) return null;
  return (
    <section className="flow-part" aria-labelledby="flow-calls">
      <h3 id="flow-calls">Calls by condition</h3>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Call</th>
              <th scope="col">Service</th>
              <th scope="col">How</th>
              <th scope="col">Runs when</th>
              <th scope="col">Certainty</th>
            </tr>
          </thead>
          <tbody>
            {calls.map((call) => (
              <tr key={call.id}>
                <th scope="row">
                  <span className="flow-ref">{call.id}</span>
                </th>
                <td>
                  {call.targetId !== null ? (
                    <ServiceLink name={call.target} />
                  ) : (
                    <code>{call.target}</code>
                  )}
                </td>
                <td>{call.how}</td>
                <td>
                  <RichText segments={call.runsWhen} />
                </td>
                <td>
                  <span className={`chip certainty-${call.certainty}`}>{call.certainty}</span>
                  {call.assumptions !== null ? (
                    <span className="muted"> ({call.assumptions})</span>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <More count={hidden} noun="call" />
    </section>
  );
}

function TextList({
  title,
  items,
  hidden,
  noun,
}: {
  title: string;
  items: readonly Segment[][];
  hidden: number;
  noun: string;
}) {
  if (items.length === 0 && hidden === 0) return null;
  return (
    <section className="flow-part" aria-label={title}>
      <h3>{title}</h3>
      <ul className="link-list">
        {items.map((item, index) => (
          <li key={String(index)}>
            <RichText segments={item} />
          </li>
        ))}
      </ul>
      <More count={hidden} noun={noun} />
    </section>
  );
}

function Cell({ segments }: { segments: readonly Segment[] }) {
  return segments.length > 0 ? <RichText segments={segments} /> : <span>-</span>;
}

function More({ count, noun }: { count: number; noun: string }) {
  if (count <= 0) return null;
  return <p className="note">And {plural(count, `more ${noun}`)} not shown.</p>;
}

function ServiceLink({ name }: { name: string }) {
  return (
    <Link to={servicePath(name)} className="code-link">
      <code>{name}</code>
    </Link>
  );
}

function plural(count: number, noun: string): string {
  return `${String(count)} ${noun}${count === 1 ? "" : "s"}`;
}

function unlinked(segments: readonly Segment[]): Segment[] {
  return segments.map((segment) => (segment.kind === "code" ? { ...segment, ref: null } : segment));
}

function codeOf(segments: readonly Segment[]): string {
  const code = segments.find((segment) => segment.kind === "code");
  return code?.kind === "code" ? code.code : "";
}
