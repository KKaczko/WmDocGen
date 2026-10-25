import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

const heading = (page: Page) => page.getByRole("heading", { level: 1 });

test("the first journey, end to end", async ({ page }) => {
  // 1. Search from the overview.
  await page.goto("/");
  await expect(heading(page)).toHaveText("Integration Server overview");
  await page.keyboard.press("/");
  await page.getByRole("combobox", { name: "Search services and packages" }).fill("createOrd");
  await expect(page.getByRole("option").first()).toContainText("orders.api:createOrder");

  // 2. Open it: what it does, its signature and calls.
  await page.keyboard.press("Enter");
  await expect(heading(page)).toHaveText("createOrder");
  await expect(page.getByText("AI-written, approved by a reviewer").first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Calls" })).toContainText(
    "Outside the analysed packages",
  );

  // 3. The graph shows the REST handler calling it.
  const graph = page.getByRole("group", { name: /^Call graph around/ });
  await expect(graph.getByRole("link", { name: "Open orders.rest.order:_post" })).toBeVisible();

  // 4. Follow the adapter call from the graph.
  await graph.getByRole("link", { name: "Open orders.db:insertOrder" }).click();
  await expect(heading(page)).toHaveText("insertOrder");
  await expect(page.getByRole("region", { name: "Adapter configuration" })).toContainText("Insert");

  // 5. Back to the caller.
  await page.goBack();
  await expect(heading(page)).toHaveText("createOrder");

  // 6. Its package: entry points and the packages it calls.
  await page
    .getByRole("list", { name: "Service facts" })
    .getByRole("link", { name: "OrdersApi" })
    .click();
  await expect(heading(page)).toHaveText("OrdersApi");
  const entries = page.getByRole("region", { name: "Entry points" });
  await expect(entries).toContainText("JMS trigger");
  const others = page.getByRole("region", { name: "Other packages" });
  await expect(others.getByRole("link", { name: "OrdersDb" })).toBeVisible();

  // 7. An entry point leads to its service.
  await entries.getByRole("link", { name: "orders.api:cancelOrder" }).click();
  await expect(heading(page)).toHaveText("cancelOrder");
});

test("the overview lists packages, sorts them and opens one", async ({ page }) => {
  await page.goto("/");
  const overview = page.getByRole("region", { name: "Overview" });
  await expect(overview.getByText("AI-written, approved by a reviewer")).toBeVisible();
  await expect(overview.getByText("Business areas")).toBeVisible();

  const packages = page.getByRole("region", { name: "Packages", exact: true });
  const firstPackage = () => packages.getByRole("row").nth(1).getByRole("link");
  await expect(firstPackage()).toHaveText("CommonUtils");
  await packages.getByRole("button", { name: "Services" }).click();
  await expect(firstPackage()).toHaveText(/^Demo/);

  await packages.getByRole("link", { name: "OrdersDb" }).click();
  await expect(heading(page)).toHaveText("OrdersDb");
  await expect(page.getByText("AI draft, not reviewed")).toBeVisible();
});

test("search opens a package page", async ({ page }) => {
  await page.goto("/");
  await expect(heading(page)).toBeVisible();
  const search = page.getByRole("combobox", { name: "Search services and packages" });
  await search.fill("CustomerApi");
  await page.getByRole("option", { name: /^CustomerApi/ }).click();
  await expect(heading(page)).toHaveText("CustomerApi");
  await expect(page).toHaveURL(/#\/p\/CustomerApi$/);
});

test("the services of a package can be filtered", async ({ page }) => {
  await page.goto("/#/p/OrdersApi");
  await expect(heading(page)).toHaveText("OrdersApi");
  const services = page.getByRole("region", { name: "Services" });
  await expect(services.getByText("7 of 7 shown")).toBeVisible();
  await services.getByLabel("Filter").fill("rest");
  await expect(services.getByText("2 of 7 shown")).toBeVisible();
  await services.getByLabel("Type").selectOption("java");
  await expect(services.getByText("0 of 7 shown")).toBeVisible();
});

test("an unknown package says it is not in this export", async ({ page }) => {
  await page.goto("/#/p/NoSuchPackage");
  await expect(heading(page)).toHaveText("Not in this export");
});

for (const [label, path] of [
  ["a package page", "/#/p/OrdersApi"],
  ["a package without overview", "/#/p/Demo001"],
] as const) {
  test(`no serious accessibility violations on ${label}`, async ({ page }) => {
    await page.goto(path);
    await expect(heading(page)).toBeVisible();
    await expect(page.getByRole("region", { name: "Services" })).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    const serious = results.violations
      .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
      .map((violation) => `${violation.id}: ${violation.nodes.map((n) => n.target).join(" | ")}`);
    expect(serious).toEqual([]);
  });
}
