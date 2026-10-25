import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

// Fail on any console error and record every request the page makes.
function watch(page: Page): { errors: string[]; requests: string[] } {
  const seen = { errors: [] as string[], requests: [] as string[] };
  page.on("console", (message) => {
    if (message.type() === "error") seen.errors.push(message.text());
  });
  page.on("pageerror", (error) => seen.errors.push(error.message));
  page.on("request", (request) => seen.requests.push(request.url()));
  return seen;
}

test("the home page names the dataset and the server size", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Integration Server overview");
  await expect(page.getByText("Synthetic demo data")).toBeVisible();
  await expect(page.getByRole("cell", { name: "OrdersApi" })).toBeVisible();
  expect(seen.errors).toEqual([]);
});

test("search, open a service, follow a call and come back", async ({ page, baseURL }) => {
  const seen = watch(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  // 1. "/" focuses the search; the service is the first result.
  await page.keyboard.press("/");
  const search = page.getByRole("combobox", { name: "Search services and packages" });
  await expect(search).toBeFocused();
  await search.fill("createOrd");
  const options = page.getByRole("option");
  await expect(options.first()).toContainText("orders.api:createOrder");

  // 2. Enter opens it: identity, signature and calls with every kind of status.
  await search.press("Enter");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("createOrder");
  await expect(page.getByText("orders.api:createOrder", { exact: true }).first()).toBeVisible();
  const calls = page.getByRole("table").filter({ hasText: "Status" }).first();
  await expect(calls.getByRole("row", { name: /orders\.db:insertOrder/ })).toContainText(
    "In these packages",
  );
  await expect(calls.getByRole("row", { name: /pub\.client:http/ })).toContainText(
    "Built-in service",
  );
  await expect(calls.getByRole("row", { name: /billing\.api:postInvoice/ })).toContainText(
    "Outside the analysed packages",
  );
  await expect(page.getByText("order", { exact: true })).toBeVisible();
  await expect(page.getByText("orders.rest.order:_post")).toBeVisible();

  // 4. Follow the adapter call: an opaque service, said plainly.
  await page.getByRole("link", { name: "orders.db:insertOrder" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("insertOrder");
  await expect(page.getByText("JDBC adapter service")).toBeVisible();
  await expect(page.getByText("Not analysed (opaque)").first()).toBeVisible();

  // 5. Back returns to the caller.
  await page.goBack();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("createOrder");

  expect(seen.errors).toEqual([]);
  // Offline by construction: every request stays on the explorer's own origin.
  expect(seen.requests.filter((url) => !url.startsWith(baseURL ?? "http://127.0.0.1"))).toEqual(
    [],
  );
});

test("a dynamic call is shown as a boundary, not as a guessed target", async ({ page }) => {
  await page.goto(`/#/s/${encodeURIComponent("orders.api.routing:routeOrder")}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("routeOrder");
  await expect(page.getByText("Java service", { exact: true })).toBeVisible();
  await expect(page.getByText("Decided at run time")).toBeVisible();
});

test("a hub service lists its many callers", async ({ page }) => {
  await page.goto(`/#/s/${encodeURIComponent("common.error:handleError")}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("handleError");
  const callers = page.getByRole("region", { name: "Called by" }).getByRole("link");
  expect(await callers.count()).toBeGreaterThan(25);
});

test("an unknown service says it is not in this export", async ({ page }) => {
  await page.goto(`/#/s/${encodeURIComponent("nothing.here:atAll")}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Not in this export");
});

test("the server sends a strict content security policy", async ({ request }) => {
  const response = await request.get("/");
  expect(response.headers()["content-security-policy"]).toContain("script-src 'self'");
  expect(response.headers()["x-content-type-options"]).toBe("nosniff");
});
