import { expect, test } from "@playwright/test";
import { analyseAndOpenStudio, JOBS, signIn } from "./helpers";

test("onboarding: create an account with a persona", async ({ page }) => {
  const email = `new-${Date.now()}@example.com`;
  await page.goto("/login");
  await page.getByRole("tab", { name: "Create account" }).click();
  await page.getByLabel("Name").fill("New Freelancer");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("secret-pass");
  await page.getByLabel(/ML engineer/).check();
  await page.getByRole("button", { name: "Create account" }).last().click();
  await expect(page.getByRole("heading", { name: "Inbox" })).toBeVisible();
  await expect(page.getByText("No jobs here yet")).toBeVisible();
  await page.goto("/settings");
  await expect(page.getByText("GigSim marketplace")).toBeVisible();
});

test("approving a proposal submits it, with evidence shown on hover", async ({ page }) => {
  await signIn(page);
  await analyseAndOpenStudio(page, JOBS.approve);
  const chip = page.getByRole("button", { name: /^Evidence \d+$/ }).first();
  await chip.hover();
  await expect(page.getByRole("tooltip")).toBeVisible();
  await expect(page.getByText(/Costs \d+ Connects/)).toBeVisible();
  await page.getByTestId("approve").click();
  await expect(page.getByTestId("approval-result")).toContainText("Submitted");
  await page.goto("/pipeline");
  await expect(page.getByRole("region", { name: "Replied" }).or(page.getByRole("region", { name: "Viewed" }))
    .or(page.getByRole("region", { name: "Lost" })).or(page.getByRole("region", { name: "Interview" })).first()).toBeVisible();
});

test("rejecting with a reason", async ({ page }) => {
  await signIn(page);
  await analyseAndOpenStudio(page, JOBS.reject);
  await page.getByRole("button", { name: "Reject" }).click();
  await page.getByLabel("Reason").fill("Not my niche right now");
  await page.getByTestId("confirm-reject").click();
  await expect(page.getByTestId("approval-result")).toContainText("Rejected");
});

test("editing a draft re-runs compliance and asks again", async ({ page }) => {
  await signIn(page);
  await analyseAndOpenStudio(page, JOBS.edit);
  await page.getByRole("button", { name: "Edit" }).click();
  await page.getByTestId("paragraph-0").fill(
    "I have built Google Sheets calculators like this before and would start by agreeing your key inputs. 100% guaranteed.",
  );
  await page.getByTestId("save-edit").click();
  await expect(page.getByTestId("approval-result")).toContainText("Needs your approval");
  await page.reload();
  await expect(page.getByTestId("cover-letter")).toContainText("Google Sheets calculators");
  await expect(page.getByTestId("cover-letter")).not.toContainText("guaranteed");   // compliance removed it
  await page.getByTestId("approve").click();
  await expect(page.getByTestId("approval-result")).toContainText("Submitted");
});

test("degraded mode: banner when the marketplace is down", async ({ page, request }) => {
  await signIn(page);
  await request.post("http://127.0.0.1:8000/e2e/marketplace", { data: { down: true } });
  try {
    await page.reload();
    await expect(page.getByTestId("marketplace-banner")).toBeVisible();
    await expect(page.getByTestId("marketplace-banner")).toContainText("Marketplace unavailable");
  } finally {
    await request.post("http://127.0.0.1:8000/e2e/marketplace", { data: { down: false } });
  }
});
