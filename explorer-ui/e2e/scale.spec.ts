import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

// Budgets from the explorer plan, measured on ~7,300 synthetic services and 9,600 document
// types served by `wm-doc explorer serve` (no compression). Run with `npm run e2e:scale`.
// Browser timings include Playwright's own round trips, so they are upper bounds.

const heading = (page: Page) => page.getByRole("heading", { level: 1 });

function report(name: string, value: number | string): void {
  test.info().annotations.push({ type: name, description: String(value) });
  console.log(`${name}: ${String(value)}`);
}

function percentile(values: number[], share: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * share))] ?? Number.NaN;
}

test("initial transfer and time until search works", async ({ page }) => {
  let bytes = 0;
  page.on("response", (response) => {
    void response.body().then(
      (body) => {
        bytes += body.length;
      },
      () => undefined,
    );
  });
  const started = Date.now();
  await page.goto("/");
  const search = page.getByRole("combobox", { name: "Search services and packages" });
  await search.fill("step012");
  await expect(page.getByRole("option").first()).toBeVisible();
  const usable = Date.now() - started;
  await page.waitForLoadState("networkidle");
  report("search usable ms", usable);
  report("initial transfer MB", (bytes / 1e6).toFixed(2));
  expect(usable).toBeLessThan(1500);
  expect(bytes).toBeLessThan(3_000_000);
});

test("search keeps up with typing", async ({ page }) => {
  await page.goto("/");
  await expect(heading(page)).toBeVisible();
  await page.getByRole("combobox", { name: "Search services and packages" }).focus();
  const times: number[] = [];
  for (const text of [
    "s",
    "st",
    "ste",
    "step",
    "step01",
    "demo12",
    "flows",
    "handle",
    "orders",
    "zz",
  ]) {
    // Measured inside the page, from the input event to the next painted frame, so the
    // number is what a person typing sees (Playwright's own round trips are left out).
    const elapsed = await page.evaluate(async (value) => {
      const input = document.querySelector<HTMLInputElement>('input[role="combobox"]');
      const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
      if (input === null || setValue === undefined) throw new Error("no search box");
      const started = performance.now();
      setValue.call(input, value);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      return performance.now() - started;
    }, text);
    await expect(page.getByRole("combobox", { name: "Search services and packages" })).toHaveValue(
      text,
    );
    times.push(elapsed);
  }
  const p95 = percentile(times, 0.95);
  report("search p95 ms (input to painted frame)", Math.round(p95));
  // Two frames of waiting are included (up to about 33 ms at 60 Hz).
  expect(p95).toBeLessThan(100);
});

test("a service opens quickly", async ({ page }) => {
  await page.goto("/");
  await expect(heading(page)).toBeVisible();
  const search = page.getByRole("combobox", { name: "Search services and packages" });
  await search.fill("demo150.flows:step012");
  await expect(page.getByRole("option").first()).toBeVisible();
  const started = Date.now();
  await search.press("Enter");
  await expect(heading(page)).toHaveText("step012");
  const opened = Date.now() - started;
  report("open service ms", opened);
  expect(opened).toBeLessThan(300);
});

test("the graph of a hub with thousands of callers stays bounded and fast", async ({ page }) => {
  await page.goto("/");
  await expect(heading(page)).toBeVisible();
  const started = Date.now();
  await page.goto("/#/s/common.error%3AhandleError?dir=callers&depth=2");
  await expect(page.locator(".react-flow__node").first()).toBeVisible();
  const shown = Date.now() - started;
  const nodes = await page.locator(".react-flow__node").count();
  report("hub graph ms", shown);
  report("hub graph nodes", nodes);
  expect(nodes).toBeLessThanOrEqual(150 + 30);
  expect(shown).toBeLessThan(2000);
  await expect(
    page.getByRole("button", { name: /more callers of common\.error:handleError$/ }),
  ).toBeVisible();
});

test("the largest package page renders", async ({ page }) => {
  const started = Date.now();
  await page.goto("/#/p/Demo001");
  await expect(heading(page)).toHaveText("Demo001");
  await expect(
    page.getByRole("region", { name: "Services" }).getByRole("row").nth(1),
  ).toBeVisible();
  report("package page ms", Date.now() - started);
});
