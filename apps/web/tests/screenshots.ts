// Capture the main screens for the README and for visual review:
//   (servers running) npx tsx tests/screenshots.ts   or   node --experimental-strip-types tests/screenshots.ts
import { chromium } from "@playwright/test";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const OUT = "../../docs/images";

const browser = await chromium.launch({ channel: process.platform === "win32" ? "msedge" : "chromium" });
const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
await page.goto(`${BASE}/login`);
await page.getByLabel("Email").fill("reviewer@gigbid.dev");
await page.getByLabel("Password").fill("gigbid-review");
await page.getByRole("button", { name: "Sign in" }).last().click();
await page.getByRole("heading", { name: "Inbox" }).waitFor();
for (const job of ["job-01c6acb86f4c", "job-2bbd7d31b158", "job-0db2b55c92a4"]) {
  await page.getByLabel("Job id").fill(job);
  await page.getByRole("button", { name: "Analyse", exact: true }).click();
  await page.getByRole("status").filter({ hasText: `Analysing ${job}` }).waitFor({ timeout: 60_000 });
}
await page.reload();
await page.waitForTimeout(1500);
await page.screenshot({ path: `${OUT}/inbox.png`, fullPage: true });
await page.goto(`${BASE}/jobs/job-01c6acb86f4c`);
await page.getByText("Requirement → evidence").waitFor();
await page.screenshot({ path: `${OUT}/job-detail.png`, fullPage: true });
await page.goto(`${BASE}/studio/job-01c6acb86f4c`);
await page.getByTestId("approve").waitFor();
await page.getByRole("button", { name: /^Evidence \d+$/ }).first().hover();
await page.screenshot({ path: `${OUT}/studio.png`, fullPage: true });
await page.goto(`${BASE}/settings`);
await page.getByText("What GigBid has learned").waitFor();
await page.screenshot({ path: `${OUT}/settings.png`, fullPage: true });
const phone = await browser.newPage({ viewport: { width: 393, height: 851 }, isMobile: true });
await phone.context().addCookies(await page.context().cookies());
await phone.goto(`${BASE}/inbox`);
await phone.getByRole("heading", { name: "Inbox" }).waitFor();
await phone.screenshot({ path: `${OUT}/inbox-phone.png`, fullPage: true });
await browser.close();
console.log("screenshots written to docs/images");
