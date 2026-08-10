/**
 * One-off screenshot capture for Parcel Selection Map UI slice.
 * Requires API on :8001 and Vite on :5173.
 */
import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "..", "screenshots");
const base = "http://127.0.0.1:5173";

async function waitMapTiles(page) {
  await page.waitForTimeout(1200);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  // 1) Initial address entry
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await waitMapTiles(page);
  await page.screenshot({
    path: path.join(outDir, "20-parcel-initial-address.png"),
    fullPage: true,
  });

  // 2) One candidate
  await page.getByTestId("resolve-property").click();
  await page.getByText(/One candidate ready/i).waitFor({ timeout: 15000 });
  await waitMapTiles(page);
  await page.screenshot({
    path: path.join(outDir, "21-parcel-one-candidate.png"),
    fullPage: true,
  });

  // 3) Confirmed parcel
  await page.getByRole("button", { name: /Confirm this parcel/i }).click();
  await page.getByText(/Parcel boundary confirmed/i).waitFor({ timeout: 15000 });
  await waitMapTiles(page);
  await page.screenshot({
    path: path.join(outDir, "22-parcel-confirmed.png"),
    fullPage: true,
  });

  // 4) Multiple candidates
  await page.getByRole("button", { name: /Multiple candidates \(demo\)/i }).click();
  await page.getByTestId("resolve-property").click();
  await page.getByText(/Multiple candidates/i).waitFor({ timeout: 15000 });
  await waitMapTiles(page);
  await page.screenshot({
    path: path.join(outDir, "23-parcel-multiple-candidates.png"),
    fullPage: true,
  });

  // 5) LIVE blocked
  await page.getByRole("button", { name: /^LIVE$/i }).click();
  await page.getByLabel(/Parcel address/i).fill("999 Unknown Ranch Rd, Nowhere, CO 80000");
  await page.getByTestId("resolve-property").click();
  await page.getByText(/blocked or not configured/i).waitFor({ timeout: 15000 });
  await waitMapTiles(page);
  await page.screenshot({
    path: path.join(outDir, "24-parcel-live-blocked.png"),
    fullPage: true,
  });

  // 6) Mobile
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: /FIXTURE \(demo\)/i }).click();
  await page.getByRole("button", { name: /One candidate \(demo\)/i }).click();
  await page.getByTestId("resolve-property").click();
  await page.getByText(/One candidate ready/i).waitFor({ timeout: 15000 });
  await waitMapTiles(page);
  await page.screenshot({
    path: path.join(outDir, "25-parcel-mobile.png"),
    fullPage: true,
  });

  await browser.close();
  console.log("Screenshots written to", outDir);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
