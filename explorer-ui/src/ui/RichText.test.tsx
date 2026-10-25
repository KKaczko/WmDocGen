import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { PathStep, Segment } from "../contract";
import { PathChain, RichText } from "./RichText";

function html(segments: Segment[]): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <RichText segments={segments} />
    </MemoryRouter>,
  );
}

describe("RichText", () => {
  it("renders hostile text as escaped text, never as markup", () => {
    const out = html([
      { kind: "text", text: '<img src=x onerror="window.__pwned=1"></b><script>x</script>' },
      { kind: "text", text: " javascript:alert(1) &lt;b&gt;" },
    ]);
    expect(out).not.toContain("<img");
    expect(out).not.toContain("<script");
    expect(out).not.toContain("</b>");
    expect(out).toContain("&lt;img src=x onerror=&quot;window.__pwned=1&quot;&gt;");
    expect(out).toContain("&amp;lt;b&amp;gt;");
    expect(out).not.toContain('href="javascript');
  });

  it("links only code segments that carry a service ID", () => {
    const out = html([
      { kind: "code", code: "orders.api:createOrder", ref: "0123456789abcdef" },
      { kind: "code", code: "billing.api:postInvoice", ref: null },
      { kind: "code", code: "javascript:alert(1)", ref: null },
    ]);
    expect(out.match(/<a /g)).toHaveLength(1);
    expect(out).toContain('href="/s/orders.api%3AcreateOrder"');
    expect(out).toContain("<code>billing.api:postInvoice</code>");
    expect(out).toContain("<code>javascript:alert(1)</code>");
  });

  it("encodes names in link paths so they cannot break out of the route", () => {
    const out = html([{ kind: "code", code: "a.b:c/../../x?y#z", ref: "0123456789abcdef" }]);
    expect(out).toContain('href="/s/a.b%3Ac%2F..%2F..%2Fx%3Fy%23z"');
  });
});

describe("PathChain", () => {
  it("links analysed services and keeps the others as text", () => {
    const steps: PathStep[] = [
      { name: "orders.rest.order:_post", id: "0123456789abcdef" },
      { name: "outside.api:thing", id: null },
    ];
    const out = renderToStaticMarkup(
      <MemoryRouter>
        <PathChain steps={steps} />
      </MemoryRouter>,
    );
    expect(out.match(/<a /g)).toHaveLength(1);
    expect(out).toContain("<code>outside.api:thing</code>");
  });
});
