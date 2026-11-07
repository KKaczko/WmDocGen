import AxeBuilder from "@axe-core/playwright";
import type { Locator, Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

// The conditional flow of orders.api:processOrder (synthetic demo): two BRANCHes, a literal
// MAPSET that is never exported, and an EXIT $flow with a failure message that is never shown.
const PROCESS = "/#/s/orders.api%3AprocessOrder";

async function openService(page: Page): Promise<Locator> {
  await page.goto(PROCESS);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("processOrder");
  return page.getByRole("region", { name: "Conditional flow" });
}

async function openFlow(page: Page): Promise<Locator> {
  const section = await openService(page);
  await section.getByText(/Show when each step runs/).click();
  await expect(section.getByRole("heading", { name: "Outline" })).toBeVisible();
  return section;
}

test("the flow loads only when opened and follows a call to its service", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  const section = await openService(page);
  await expect(section.getByText(/2 decisions, 5 calls, 1 EXIT step/)).toBeVisible();
  expect(requests.filter((url) => url.includes("/data/flows/"))).toEqual([]);

  await section.getByText(/Show when each step runs/).click();
  await expect(section.getByRole("heading", { name: "Outline" })).toBeVisible();
  expect(requests.filter((url) => url.includes("/data/flows/"))).toHaveLength(1);

  const decision = section.getByRole("region", { name: /^D1 BRANCH on/ });
  await expect(decision.getByRole("row", { name: /D1\.c1 .*ACTIVE/ })).toBeVisible();
  await expect(decision.getByRole("row", { name: /D1\.c3 no other case matches/ })).toBeVisible();
  // D2 has no $default, so it also says what happens when no case matches.
  const second = section.getByRole("region", { name: /^D2 BRANCH on/ });
  await expect(second.getByRole("row", { name: /no case matches/ })).toBeVisible();

  const outline = section.locator(".flow-outline").first();
  await outline.locator("summary", { hasText: /^D1 BRANCH/ }).click();
  await outline.locator("summary", { hasText: /^D1\.c1 when/ }).click();
  await outline.getByRole("link", { name: "orders.api:validateOrder" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("validateOrder");
});

test("calls and field origins carry certainty and never show the literal", async ({ page }) => {
  const section = await openFlow(page);

  const calls = section.getByRole("region", { name: "Calls by condition" });
  const first = calls.getByRole("row", { name: /^C1 / });
  await expect(first.getByText("derived")).toBeVisible();
  await expect(first.getByRole("link", { name: "orders.api:validateOrder" })).toBeVisible();

  const second = section.getByRole("region", { name: /^D2 BRANCH on/ });
  await expect(second.getByText(/set to a literal \(literal, not exported\)/)).toBeVisible();
  await expect(second.getByText("observed").first()).toBeVisible();
  await expect(second.getByText("from the FLOW").first()).toBeVisible();
  await expect(page.getByText("UNCHECKED")).toHaveCount(0);
  await expect(page.getByText(/Rejected/)).toHaveCount(0);

  const scenarios = section.getByRole("region", { name: "Scenarios" });
  await expect(scenarios.getByRole("heading", { name: "D1, D2" })).toBeVisible();
});

test("the flow works by keyboard", async ({ page }) => {
  const section = await openService(page);
  await section.locator("summary").first().focus();
  await page.keyboard.press("Enter");
  await expect(section.getByRole("heading", { name: "Outline" })).toBeVisible();

  const branch = section.locator(".flow-outline summary", { hasText: /^D1 BRANCH/ });
  await branch.focus();
  await page.keyboard.press("Enter");
  await expect(section.locator(".flow-outline summary", { hasText: /^D1\.c1 when/ })).toBeVisible();
});

test("the open flow has no CSP and no serious accessibility violations", async ({ page }) => {
  await page.addInitScript(() => {
    const seen: string[] = [];
    (window as unknown as { __violations: string[] }).__violations = seen;
    document.addEventListener("securitypolicyviolation", (event) => {
      seen.push(event.violatedDirective);
    });
  });
  const section = await openFlow(page);
  for (const summary of await section.locator(".flow-outline summary").all()) {
    if (await summary.isVisible()) await summary.click();
  }

  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const serious = results.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => `${violation.id}: ${violation.nodes.map((n) => n.target).join(" | ")}`);
  expect(serious).toEqual([]);
  const violations = await page.evaluate(
    () => (window as unknown as { __violations: string[] }).__violations,
  );
  expect(violations).toEqual([]);
});
