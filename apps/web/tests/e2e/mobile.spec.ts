import { expect, test } from "@playwright/test";
import { JOBS, signIn } from "./helpers";

// Phone layout: navigation via the menu, and the studio usable without horizontal page scroll.
test("works on a phone screen", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: /Menu/ }).click();
  await page.locator("#mobile-nav").getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await page.goto("/inbox");
  await page.getByLabel("Job id").fill(JOBS.mobile);
  await page.getByRole("button", { name: "Analyse", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: `Analysing ${JOBS.mobile}` })).toBeVisible({ timeout: 60_000 });
  await page.goto(`/studio/${JOBS.mobile}`);
  await expect(page.getByTestId("approve")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
