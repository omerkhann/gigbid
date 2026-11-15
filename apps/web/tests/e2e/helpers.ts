import { expect, type Page } from "@playwright/test";

// Data-analyst jobs from the dev set that GigBid recommends bidding on. Each test uses its own job.
export const JOBS = {
  approve: "job-0b954e1ba14e",
  reject: "job-27d167db8b63",
  edit: "job-276f63f76290",
  mobile: "job-24da7222feb9",
};

export async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("reviewer@gigbid.dev");
  await page.getByLabel("Password").fill("gigbid-review");
  await page.getByRole("button", { name: "Sign in" }).last().click();
  await expect(page.getByRole("heading", { name: "Inbox" })).toBeVisible();
}

/** Analyse a job from the inbox form and open its proposal studio once it awaits approval. */
export async function analyseAndOpenStudio(page: Page, jobId: string) {
  await page.getByLabel("Job id").fill(jobId);
  await page.getByRole("button", { name: "Analyse" }).click();
  await page.goto(`/jobs/${jobId}`);
  await expect(page.getByText("Needs your approval").first()).toBeVisible();
  await page.getByRole("button", { name: "Review proposal" }).click();
  await expect(page.getByRole("heading", { name: /Proposal for/ })).toBeVisible();
}
