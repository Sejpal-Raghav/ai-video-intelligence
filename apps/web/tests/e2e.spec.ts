import { test, expect } from "@playwright/test";

test.describe("Warehouse Video Intelligence Web App", () => {
  test("Dashboard renders KPI cards, navigation, and responsible-AI banner", async ({ page }) => {
    await page.goto("/");

    // Verify Brand title & Header
    await expect(page.locator("h1")).toContainText("Warehouse Video Intelligence");

    // Verify Responsible AI policy banner in layout
    await expect(page.locator("body")).toContainText("Responsible AI Policy");
    await expect(page.locator("body")).toContainText("Risk event, not confirmed damage");

    // Verify Navigation links
    await expect(page.locator("header")).toContainText("Dashboard");
    await expect(page.locator("header")).toContainText("Upload Video");
    await expect(page.locator("header")).toContainText("Camera Setup");
  });

  test("Upload page renders constraints checklist and source consent requirement", async ({ page }) => {
    await page.goto("/upload");

    // Verify heading
    await expect(page.locator("h1")).toContainText("Upload Warehouse Video");

    // Verify Section 8.2 constraints checklist
    await expect(page.locator("body")).toContainText("MP4 (H.264)");
    await expect(page.locator("body")).toContainText("500 MB");
    await expect(page.locator("body")).toContainText("600s (10 min)");
    await expect(page.locator("body")).toContainText("4K (3840×2160)");

    // Verify mandatory Source Consent checkbox
    const consentCheckbox = page.locator("input[type='checkbox']");
    await expect(consentCheckbox).toBeVisible();
    await expect(page.locator("body")).toContainText("Mandatory Source Consent");

    // Verify Upload button is disabled when consent is not given
    const submitBtn = page.getByRole("button", { name: /Upload & Analyze/i });
    await expect(submitBtn).toBeDisabled();
  });

  test("Camera calibration page renders interactive editor and operator confirmation", async ({ page }) => {
    await page.goto("/settings/camera");

    // Verify heading
    await expect(page.locator("h1")).toContainText("Camera Calibration & Spatial Setup");

    // Verify Polygon editor layers
    await expect(page.locator("body")).toContainText("Floor Polygon");
    await expect(page.locator("body")).toContainText("Zones");
    await expect(page.locator("body")).toContainText("Visible Support Regions");

    // Verify Section 12.1 notice
    await expect(page.locator("body")).toContainText("Blueprint §12.1 Spatial Integrity Rules");
    await expect(page.locator("body")).toContainText("MUST be convex");

    // Verify Aspect ratio input
    const aspectInput = page.locator("input[type='number']");
    await expect(aspectInput).toBeVisible();
  });
});
