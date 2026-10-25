import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

const service = (name: string) => `/#/s/${encodeURIComponent(name)}`;

async function open(page: Page, name: string): Promise<void> {
  await page.goto(service(name));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(name.split(":")[1] ?? name);
}

test("an approved description is labelled and links the services it names", async ({ page }) => {
  await open(page, "orders.api:createOrder");
  const description = page.getByRole("region", { name: "What it does" });
  await expect(description.getByText("AI-written, approved by a reviewer")).toBeVisible();
  await expect(description.getByText("Creates an order from a REST request")).toBeVisible();
  await expect(page.getByText("Approved description")).toBeVisible();

  await description.getByRole("link", { name: "orders.db:insertOrder" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("insertOrder");
  const adapter = page.getByRole("region", { name: "Adapter configuration" });
  await expect(adapter.getByText("Insert", { exact: true })).toBeVisible();
  await expect(adapter.getByText("ORDERS, ORDER_LINES")).toBeVisible();
  await expect(adapter.getByText("Oracle")).toBeVisible();
});

test("stale, draft, edited and unverified descriptions say so", async ({ page }) => {
  await open(page, "orders.api:getOrder");
  await expect(
    page
      .getByRole("region", { name: "What it does" })
      .getByText("AI-written and approved, but the facts changed since"),
  ).toBeVisible();
  await expect(page.getByText(/facts of this service changed after/)).toBeVisible();

  await open(page, "orders.api:validateOrder");
  await expect(page.getByText("AI draft, not reviewed").first()).toBeVisible();

  await open(page, "orders.api:cancelOrder");
  await expect(page.getByText("AI draft edited by hand, not reviewed").first()).toBeVisible();
  const entry = page.getByRole("region", { name: "Entry points" });
  await expect(entry.getByText("JMS trigger")).toBeVisible();

  await open(page, "customers.api:getCustomer");
  await expect(page.getByText(/names that are not in the facts/)).toBeVisible();
  await expect(page.getByText("crm.legacy:findCustomer").first()).toBeVisible();
});

test("entry points, data effects and documents come from the facts", async ({ page }) => {
  await open(page, "orders.api:createOrder");
  const entry = page.getByRole("region", { name: "Entry points" });
  await expect(entry.getByText("HTTP POST /rest/orders/rest/order")).toBeVisible();
  await expect(entry.getByText("From static analysis")).toBeVisible();
  const effects = page.getByRole("region", { name: "Data and systems touched" });
  await expect(effects.getByText(/url \(literal, not exported\)/)).toBeVisible();
  await expect(effects.getByRole("row", { name: /inserts rows into/ })).toBeVisible();
  const documents = page.getByRole("region", { name: "Document types used" });
  await expect(documents.getByText("orders.docs:Order")).toBeVisible();
});

test("hostile description text is shown inert or withheld", async ({ page }) => {
  await page.addInitScript(() => {
    const seen: string[] = [];
    (window as unknown as { __violations: string[] }).__violations = seen;
    document.addEventListener("securitypolicyviolation", (event) => {
      seen.push(event.violatedDirective);
    });
  });
  const dialogs: string[] = [];
  page.on("dialog", (dialog) => {
    dialogs.push(dialog.message());
    void dialog.dismiss();
  });

  await open(page, "customers.api:updateCustomer");
  const description = page.getByRole("region", { name: "What it does" });
  await expect(description.getByText(/<\/b> javascript:window\.__pwned=1/)).toBeVisible();
  await expect(description.getByText("[withheld: raw HTML]")).toBeVisible();
  await expect(description.getByText("[withheld: secret-like key/value]")).toBeVisible();
  expect(await page.locator("main img, main script, main iframe").count()).toBe(0);

  const state = await page.evaluate(() => {
    const w = window as unknown as { __pwned?: unknown; __violations: string[] };
    return { pwned: w.__pwned, violations: w.__violations };
  });
  expect(state.pwned).toBeUndefined();
  expect(state.violations).toEqual([]);
  expect(dialogs).toEqual([]);
});

for (const [label, path] of [
  ["home", "/"],
  ["a FLOW service", service("orders.api:createOrder")],
  ["an adapter service", service("orders.db:insertOrder")],
  ["a hostile description", service("customers.api:updateCustomer")],
] as const) {
  test(`no serious accessibility violations on ${label}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    const serious = results.violations
      .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
      .map((violation) => `${violation.id}: ${violation.nodes.map((n) => n.target).join(" | ")}`);
    expect(serious).toEqual([]);
  });
}

test("the page never scrolls sideways at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await open(page, "orders.api:createOrder");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
