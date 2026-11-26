import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { JdbcInfo } from "../contract";
import { JdbcDetails } from "./FactsSections";

function jdbc(overrides: Partial<JdbcInfo> = {}): JdbcInfo {
  return {
    templateKind: "DynamicSQL",
    supported: true,
    hypotheses: [],
    sql: "SELECT a\nFROM t WHERE x = ? AND y IN (${IDS})",
    sqlState: "included",
    sqlLength: 42,
    statement: "SELECT",
    readStatus: "analysed",
    tables: [{ name: "t", schemaName: null, access: "read", clauses: ["FROM"] }],
    procedure: null,
    shape: ["WHERE: yes", "ORDER BY: none", "pagination: none"],
    binds: [
      {
        position: 1,
        field: "x",
        javaType: "java.lang.String",
        jdbcType: "VARCHAR",
        column: "x",
        operator: "=",
        role: "value",
      },
    ],
    substitutions: [
      {
        name: "IDS",
        field: "IDS",
        javaType: "java.lang.String",
        contexts: ["value list"],
        column: "y",
      },
    ],
    results: [],
    statementOutput: "SQLStatement",
    maxRows: "0",
    queryTimeout: "-1",
    findings: [
      {
        kind: "risk",
        code: "sql-injection-exposure",
        text: [{ kind: "text", text: "Potential SQL injection exposure." }],
        basis: "DynamicSQL text substitution",
      },
    ],
    notes: [],
    ...overrides,
  };
}

function html(info: JdbcInfo): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <JdbcDetails jdbc={info} />
    </MemoryRouter>,
  );
}

describe("JdbcDetails", () => {
  it("shows the SQL as plain text with its line breaks", () => {
    const out = html(jdbc());
    expect(out).toContain('<pre class="sql" aria-label="SQL template"><code>SELECT a\nFROM t');
    expect(out).toContain("${IDS}");
    expect(out).toContain("Potential risk:");
    expect(out).toContain("= x");
  });

  it("never turns SQL text into markup", () => {
    const out = html(jdbc({ sql: "SELECT '<img src=x onerror=alert(1)>' FROM t</code><script>" }));
    expect(out).not.toContain("<img");
    expect(out).not.toContain("<script");
    expect(out).toContain("&lt;img src=x onerror=alert(1)&gt;");
  });

  it("says why the SQL is not shown", () => {
    expect(html(jdbc({ sql: null, sqlState: "excluded" }))).toContain("--sql exclude");
    expect(html(jdbc({ sql: null, sqlState: "withheld" }))).toContain("withheld");
    expect(html(jdbc({ supported: false }))).toContain("only DynamicSQL and CustomSQL");
  });

  it("marks an unconfirmed reading", () => {
    expect(html(jdbc({ hypotheses: ["length:vlq"] }))).toContain("Unconfirmed reading");
  });
});
