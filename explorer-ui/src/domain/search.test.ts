import { describe, expect, it } from "vitest";

import type { SearchIndex, SearchService } from "../contract";
import { createSearcher, nameWords } from "./search";

function service(name: string, extra: Partial<SearchService> = {}): SearchService {
  return {
    id: name.length.toString(16).padStart(16, "0"),
    name,
    package: "OrdersApi",
    kind: "flow",
    analysis: "full",
    description: "none",
    purpose: null,
    ...extra,
  };
}

const index: SearchIndex = {
  contract: "wm-doc-explorer.v1",
  services: [
    service("orders.api:createOrder", { purpose: "Creates an order and bills it." }),
    service("orders.api:createOrderLine"),
    service("orders.db:insertOrder", { package: "OrdersDb", kind: "adapter" }),
    service("common.log:logEvent", { package: "CommonUtils" }),
    service("customers.api:getCustomer", { package: "CustomerApi" }),
  ],
  packages: [
    { id: "00000000000000aa", name: "OrdersApi", services: 2, overview: "none", purpose: null },
  ],
};
const searcher = createSearcher(index);
const names = (text: string) => searcher.query(text).map((hit) => hit.item.name);

describe("nameWords", () => {
  it("splits namespaces and camelCase", () => {
    expect(nameWords("orders.api:createOrder")).toEqual([
      "orders",
      "api",
      "createorder",
      "create",
      "order",
    ]);
    expect(nameWords("ext.HTTPClient:send")).toContain("client");
  });
});

describe("createSearcher", () => {
  it("ranks the exact short name, then prefixes, then substrings", () => {
    expect(names("createOrder")[0]).toBe("orders.api:createOrder");
    expect(names("createOrd").slice(0, 2)).toEqual([
      "orders.api:createOrder",
      "orders.api:createOrderLine",
    ]);
    expect(names("insert")).toEqual(["orders.db:insertOrder"]);
  });

  it("matches namespace segments, camelCase words and packages", () => {
    expect(names("log")).toContain("common.log:logEvent");
    expect(names("event")).toEqual(["common.log:logEvent"]);
    expect(names("customerapi")).toEqual(["customers.api:getCustomer"]);
  });

  it("requires every word and searches purpose lines", () => {
    expect(names("orders bills")).toEqual(["orders.api:createOrder"]);
    expect(names("orders nothing-like-this")).toEqual([]);
  });

  it("lists packages after services and ignores empty queries", () => {
    const hits = searcher.query("ordersapi");
    expect(hits.at(-1)?.type).toBe("package");
    expect(searcher.query("   ")).toEqual([]);
  });

  it("is deterministic and limited", () => {
    expect(names("o")).toEqual(names("o"));
    expect(searcher.query("o", { services: 2, packages: 0 })).toHaveLength(2);
  });

  it("stays fast at production size", () => {
    const big = createSearcher({
      ...index,
      services: Array.from({ length: 7300 }, (_, i) =>
        service(`pkg${String(i % 200)}.area${String(i % 37)}.flows:handleThing${String(i)}`, {
          purpose: "Reads orders from the queue and posts invoices to billing.",
        }),
      ),
    });
    const started = performance.now();
    for (const text of ["handle", "area1", "invoice", "pkg12 thing", "zzz"]) big.query(text);
    expect((performance.now() - started) / 5).toBeLessThan(50);
  });
});
