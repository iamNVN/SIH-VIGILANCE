// The "golden path" a live demo actually walks -- login, land on the
// dashboard, open a case, read every tab. Run before a demo (or after any
// change) to catch what a manual click-through would: a blank page, a
// console error, a tab that never loads. Requires the frontend
// (`npm run dev`) and a seeded, trained backend already running --
// see README.md.
//
// Run: npx playwright test

import { expect, test } from "@playwright/test";

test.describe("golden path", () => {
  test("investigator: login, scoped dashboard, sidebar, one full case", async ({ page }) => {
    const consoleErrors = [];
    page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
    page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

    await page.goto("/");
    await expect(page.getByText("Choose a demo persona to continue")).toBeVisible();
    await page.click("text=Insp. Ananya Iyer");

    await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("BENGALURU ONLY")).toBeVisible();

    // Investigators don't get Reports -- both the nav link and the guarded route.
    await expect(page.locator('a:has-text("Reports")')).toHaveCount(0);
    await page.goto("/#/analytics");
    await expect(page).not.toHaveURL(/analytics/);

    // Every sidebar destination loads without blowing up.
    for (const [label, marker] of [
      ["Cases", "Search and browse"],
      ["Network Graph", "Fraud Rings"],
      ["Predictions", "Predictions"],
      ["Alerts", "Alerts"],
      ["Settings", "Signed in as"],
    ]) {
      await page.click(`a:has-text("${label}")`);
      await expect(page.getByText(marker).first()).toBeVisible({ timeout: 10000 });
    }

    // Open a real case and walk all four tabs.
    await page.click('a:has-text("Command Center")');
    await page.waitForSelector("ul li button");
    await page.locator("ul li button").first().click();
    await expect(page.getByText("Top Predicted Cash-out Point")).toBeVisible({ timeout: 15000 });

    for (const tab of ["Fund Flow Trace", "Cash-out Prediction", "Intervention Brief"]) {
      await page.click(`text=${tab}`);
      await page.waitForTimeout(800);
    }

    expect(consoleErrors, `console errors during golden path: ${consoleErrors.join("; ")}`).toEqual([]);
  });
});
