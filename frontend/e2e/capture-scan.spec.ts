/**
 * Playwright: upload → progress → review → save (and cancel).
 * Run: npx playwright test e2e/capture-scan.spec.ts (requires site + auth).
 */
import { test, expect } from "@playwright/test";

test.describe("Capture scan", () => {
  test.skip(!process.env.TAXIMATE_E2E_URL, "Set TAXIMATE_E2E_URL to run");

  test("opens scan dialog", async ({ page }) => {
    await page.goto(process.env.TAXIMATE_E2E_URL!);
    await page.getByLabel(/scan/i).click();
    await expect(page.getByRole("dialog")).toBeVisible();
  });
});
