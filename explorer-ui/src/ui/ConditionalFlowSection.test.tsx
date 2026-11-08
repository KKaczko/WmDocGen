import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { FlowView, Segment } from "../contract";
import { FlowContent } from "./ConditionalFlowSection";

const text = (value: string): Segment => ({ kind: "text", text: value });
const code = (value: string, ref: string | null = null): Segment => ({
  kind: "code",
  code: value,
  ref,
});

const VALIDATE = "0123456789abcdef";

const FLOW: FlowView = {
  contract: "wm-doc-explorer.v1",
  serviceId: "fedcba9876543210",
  outline: [
    {
      kind: "branch",
      ref: "D1",
      text: [text("BRANCH on "), code("/order/status")],
      targetId: null,
      never: false,
      children: [
        {
          kind: "case",
          ref: "D1.c1",
          text: [code("/order/status"), text(" is "), code("ACTIVE")],
          targetId: null,
          never: false,
          children: [
            {
              kind: "call",
              ref: "C1",
              text: [code("orders.api:validateOrder", VALIDATE)],
              targetId: VALIDATE,
              never: false,
              children: [],
            },
          ],
        },
        {
          kind: "case",
          ref: "D1.c2",
          text: [text('<img src=x onerror="window.__pwned=1">')],
          targetId: null,
          never: true,
          children: [],
        },
      ],
    },
  ],
  outlineHidden: 3,
  decisions: [
    {
      id: "D1",
      heading: [text("BRANCH on "), code("/order/status")],
      evaluatedWhen: null,
      inLoop: false,
      notes: [],
      casesHidden: 0,
      cases: [
        {
          id: "D1.c1",
          condition: [code("/order/status"), text(" is "), code("ACTIVE")],
          calls: [text("C1 "), code("orders.api:validateOrder", VALIDATE)],
          ends: [],
          notes: [],
          never: false,
        },
      ],
      noMatch: [text("nothing runs and the next step follows (S7)")],
      fields: [
        {
          path: "/validationStatus",
          summary: [text("May come from any of:")],
          origins: [
            {
              text: [text("set to a literal (literal, not exported) in the MAP (line 3)")],
              certainty: "observed",
              basis: "flow-xml",
              assumptions: null,
              evidence: { path: "OrdersApi/ns/orders/api/processOrder/flow.xml", xmlPath: null },
              depth: 0,
              copied: null,
            },
            {
              text: [text("may be left by C1")],
              certainty: "possible",
              basis: "callee-signature",
              assumptions: "assumption S16",
              evidence: null,
              depth: 1,
              copied: "/valid",
            },
          ],
          originsHidden: 0,
          notes: [],
        },
      ],
      fieldsHidden: 0,
      unfollowed: [],
    },
  ],
  decisionsHidden: 0,
  calls: [
    {
      id: "C1",
      target: "orders.api:validateOrder",
      targetId: VALIDATE,
      how: "step",
      runsWhen: [text("D1 = "), code("ACTIVE")],
      certainty: "derived",
      assumptions: null,
      reach: "conditional",
    },
  ],
  callsHidden: 0,
  exits: [],
  exitsHidden: 0,
  neverRun: [],
  neverRunHidden: 0,
  scenarios: [
    {
      decisions: ["D1", "D2"],
      rows: [
        {
          id: "P1",
          conditions: [text("D1 = "), code("ACTIVE")],
          calls: [],
          ends: [],
          dependsOn: [],
          feasibility: "conditional",
          assumptions: null,
        },
      ],
      notes: [],
    },
  ],
  scenarioNotes: [],
  limits: [],
};

function html(flow: FlowView, conditionValues: "included" | "excluded" = "included"): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <FlowContent flow={flow} conditionValues={conditionValues} />
    </MemoryRouter>,
  );
}

describe("FlowContent", () => {
  it("shows ids, conditions, certainty and where a field comes from", () => {
    const out = html(FLOW);
    expect(out).toContain('<span class="flow-ref">D1</span>');
    expect(out).toContain("<code>ACTIVE</code>");
    expect(out).toContain('<span class="chip certainty-observed">observed</span>');
    expect(out).toContain('<span class="chip certainty-possible">possible</span>');
    expect(out).toContain("called service&#x27;s signature");
    expect(out).toContain("assumption S16");
    expect(out).toContain("<code>/valid</code>:");
    expect(out).toContain('<span class="chip feasibility-conditional">conditional</span>');
    expect(out).toContain("never runs");
    expect(out).toContain("And 3 more steps not shown.");
  });

  it("renders hostile text inert and links only analysed services", () => {
    const out = html(FLOW);
    expect(out).not.toContain("<img");
    expect(out).toContain("&lt;img src=x onerror=&quot;window.__pwned=1&quot;&gt;");
    // C1 as an outline leaf, in the case table and in the calls table.
    expect(out.match(/href="\/s\/orders\.api%3AvalidateOrder"/g)).toHaveLength(3);
    expect(out).not.toContain('href="javascript');
  });

  it("keeps links out of an outline summary", () => {
    const withChildren: FlowView = {
      ...FLOW,
      outline: [
        {
          kind: "call",
          ref: "C2",
          text: [code("orders.api:validateOrder", VALIDATE)],
          targetId: VALIDATE,
          never: false,
          children: [
            {
              kind: "transformer",
              ref: "C3",
              text: [code("pub.string:toUpper")],
              targetId: null,
              never: false,
              children: [],
            },
          ],
        },
      ],
    };
    const out = html(withChildren);
    const summary = /<summary>(.*?)<\/summary>/s.exec(out.split('class="flow-outline"')[1] ?? "");
    expect(summary?.[1]).not.toContain("<a ");
    expect(out).toContain('<p class="flow-open"><a');
  });

  it("says when condition values are left out", () => {
    expect(html(FLOW, "excluded")).toContain("Condition values (case labels) are not included");
    expect(html(FLOW)).not.toContain("Condition values (case labels) are not included");
  });
});
