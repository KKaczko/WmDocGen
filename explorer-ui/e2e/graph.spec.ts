import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

const service = (name: string, query = "") =>
  `/#/s/${encodeURIComponent(name)}${query === "" ? "" : `?${query}`}`;

async function openGraph(page: Page, name: string, query = ""): Promise<void> {
  await page.goto(service(name, query));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(name.split(":")[1] ?? name);
  await expect(page.locator(".react-flow__node").first()).toBeVisible();
}

const graph = (page: Page) => page.getByRole("group", { name: /^Call graph around/ });

test("the graph shows callers and callees and opens a service", async ({ page }) => {
  await openGraph(page, "orders.api:createOrder");
  await expect(
    graph(page).getByRole("link", { name: "Open orders.rest.order:_post" }),
  ).toBeVisible();
  await expect(graph(page).getByText("billing.api:postInvoice")).toBeVisible();
  await expect(graph(page).getByText("<dynamic-target>")).toBeVisible();
  expect(await page.locator(".react-flow__node").count()).toBeLessThanOrEqual(150);

  await graph(page).getByRole("link", { name: "Open orders.db:insertOrder" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("insertOrder");
});

test("graph settings live in the URL and Back restores them", async ({ page }) => {
  await openGraph(page, "orders.api:createOrder");
  await expect(graph(page).getByText("<dynamic-target>")).toBeVisible();

  await page.getByLabel("Depth").selectOption("1");
  await expect(page).toHaveURL(/depth=1/);
  await expect(graph(page).getByText("<dynamic-target>")).toHaveCount(0);

  await page.goBack();
  await expect(page.getByLabel("Depth")).toHaveValue("2");
  await expect(graph(page).getByText("<dynamic-target>")).toBeVisible();

  // The setting goes through the URL, so the box turns checked a moment after the click.
  await page.getByLabel("Built-in services").click();
  await expect(page.getByLabel("Built-in services")).toBeChecked();
  await expect(page).toHaveURL(/builtins=1/);
  await expect(graph(page).getByText("pub.client:http")).toBeVisible();
});

test("a node opens and closes its next level", async ({ page }) => {
  await openGraph(page, "orders.api:createOrder", "depth=1");
  const transform = graph(page).getByRole("link", { name: "Open common.util:transformOrder" });
  await expect(transform).toHaveCount(0);

  await graph(page)
    .getByRole("button", { name: "Show the next level from orders.api:validateOrder" })
    .click();
  await expect(transform).toBeVisible();
  await graph(page)
    .getByRole("button", { name: "Hide the next level from orders.api:validateOrder" })
    .click();
  await expect(transform).toHaveCount(0);
});

test("a hub shows '+N more' and the full list of its callers", async ({ page }) => {
  await openGraph(page, "common.error:handleError", "dir=callers&depth=1");
  const callers = graph(page).getByRole("link", { name: /^Open / });
  await expect(callers).toHaveCount(25);
  // In the canvas (it may be panned out of view) and as a button below it.
  await expect(graph(page).getByRole("button", { name: /^\+\d+ more callers$/ })).toHaveCount(1);
  await page
    .getByRole("button", { name: /^\+\d+ more callers of common\.error:handleError$/ })
    .click();
  const list = page.getByRole("region", { name: /^All \d+ callers of common\.error:handleError$/ });
  await expect(list).toBeVisible();
  expect(await list.getByRole("link").count()).toBeGreaterThan(25);
});

test("the list view shows the same neighbourhood and works by keyboard", async ({ page }) => {
  await openGraph(page, "orders.api:createOrder");
  await page.getByRole("button", { name: "Show as list" }).click();
  await expect(page).toHaveURL(/view=list/);
  const section = page.getByRole("region", { name: "Call graph" });
  const link = section.getByRole("link", { name: "orders.db:insertOrder" });
  await expect(link).toBeVisible();
  await expect(section.getByText("Callers", { exact: true })).toBeVisible();

  await link.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("insertOrder");
  await expect(page).toHaveURL(/view=list/);
});

test("the graph keeps the security policy and links nowhere outside", async ({ page }) => {
  await page.addInitScript(() => {
    const seen: string[] = [];
    (window as unknown as { __violations: string[] }).__violations = seen;
    document.addEventListener("securitypolicyviolation", (event) => {
      seen.push(`${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await openGraph(page, "orders.api:createOrder");
  const violations = await page.evaluate(
    () => (window as unknown as { __violations: string[] }).__violations,
  );
  expect(violations).toEqual([]);
  expect(errors).toEqual([]);
  expect(await page.locator('a[href^="http"]').count()).toBe(0);
});

test("no serious accessibility violations with the graph open", async ({ page }) => {
  await openGraph(page, "orders.api:createOrder");
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const serious = results.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => `${violation.id}: ${violation.nodes.map((n) => n.target).join(" | ")}`);
  expect(serious).toEqual([]);
});

test("the graph appears quickly", async ({ page }) => {
  const started = Date.now();
  await openGraph(page, "demo001.flows:step000", "depth=4&limit=300");
  expect(Date.now() - started).toBeLessThan(3000);
});
