# File Upload & Download Testing

> For advanced patterns (progress tracking, cancellation, retry logic), see [file-upload-download.md](./file-upload-download.md)

## Table of Contents

1. [File Downloads](#file-downloads)
2. [File Uploads](#file-uploads)
3. [Drag and Drop](#drag-and-drop)
4. [File Content Verification](#file-content-verification)

## File Downloads

### Basic Download

```typescript
test("download PDF report", async ({ page }) => {
  await page.goto("/reports");

  // Start waiting for download before clicking
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PDF" }).click();
  const download = await downloadPromise;

  // Verify filename
  expect(download.suggestedFilename()).toBe("report.pdf");

  // Save to specific path
  await download.saveAs("./downloads/report.pdf");
});
```

### Download with Custom Path

```typescript
test("download to temp directory", async ({ page }, testInfo) => {
  await page.goto("/exports");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export CSV" }).click();
  const download = await downloadPromise;

  // Save to test output directory
  const path = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(path);

  // Attach to test report
  await testInfo.attach("downloaded-file", { path });
});
```

### Verify Download Content

```typescript
import fs from "fs";
import path from "path";

test("verify CSV content", async ({ page }, testInfo) => {
  await page.goto("/data");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export" }).click();
  const download = await downloadPromise;

  const filePath = testInfo.outputPath("export.csv");
  await download.saveAs(filePath);

  // Read and verify content
  const content = fs.readFileSync(filePath, "utf-8");
  expect(content).toContain("Name,Email,Status");
  expect(content).toContain("John Doe");

  // Verify row count
  const rows = content.trim().split("\n");
  expect(rows.length).toBeGreaterThan(1);
});
```

### Multiple Downloads

```typescript
test("download multiple files", async ({ page }) => {
  await page.goto("/batch-export");

  await page.getByRole("checkbox", { name: "Select All" }).check();

  // Collect all downloads
  const downloads: Download[] = [];
  page.on("download", (download) => downloads.push(download));

  await page.getByRole("button", { name: "Download Selected" }).click();

  // Wait for all downloads
  await expect.poll(() => downloads.length, { timeout: 30000 }).toBe(5);

  // Verify each download
  for (const download of downloads) {
    expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  }
});
```

### Download Fixture

```typescript
// fixtures/download.fixture.ts
import { test as base, Download } from "@playwright/test";
import fs from "fs";
import path from "path";

type DownloadFixtures = {
  downloadDir: string;
  downloadAndVerify: (
    trigger: () => Promise<void>,
    expectedFilename: string,
  ) => Promise<string>;
};

export const test = base.extend<DownloadFixtures>({
  downloadDir: async ({}, use, testInfo) => {
    const dir = testInfo.outputPath("downloads");
    fs.mkdirSync(dir, { recursive: true });
    await use(dir);
  },

  downloadAndVerify: async ({ page, downloadDir }, use) => {
    await use(async (trigger, expectedFilename) => {
      const downloadPromise = page.waitForEvent("download");
      await trigger();
      const download = await downloadPromise;

      expect(download.suggestedFilename()).toBe(expectedFilename);

      const filePath = path.join(downloadDir, expectedFilename);
      await download.saveAs(filePath);
      return filePath;
    });
  },
});
```

## File Uploads

### Basic Upload

```typescript
test("upload profile picture", async ({ page }) => {
  await page.goto("/settings/profile");

  // Upload file
  await page
    .getByLabel("Profile Picture")
    .setInputFiles("./fixtures/avatar.png");

  // Verify preview
  await expect(page.getByAltText("Profile preview")).toBeVisible();

  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Profile updated")).toBeVisible();
});
```

### Multiple File Upload

```typescript
test("upload multiple documents", async ({ page }) => {
  await page.goto("/documents/upload");

  await page
    .getByLabel("Documents")
    .setInputFiles([
      "./fixtures/doc1.pdf",
      "./fixtures/doc2.pdf",
      "./fixtures/doc3.pdf",
    ]);

  // Verify all files listed
  await expect(page.getByText("doc1.pdf")).toBeVisible();
  await expect(page.getByText("doc2.pdf")).toBeVisible();
  await expect(page.getByText("doc3.pdf")).toBeVisible();

  await page.getByRole("button", { name: "Upload All" }).click();
  await expect(page.getByText("3 files uploaded")).toBeVisible();
});
```

### Upload with File Chooser

```typescript
test("upload via file chooser dialog", async ({ page }) => {
  await page.goto("/upload");

  // Handle file chooser
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Choose File" }).click();
  const fileChooser = await fileChooserPromise;

  await fileChooser.setFiles("./fixtures/document.pdf");

  await expect(page.getByText("document.pdf")).toBeVisible();
});
```

### Clear and Re-upload

```typescript
test("replace uploaded file", async ({ page }) => {
  await page.goto("/upload");

  const input = page.getByLabel("Document");

  // Upload first file
  await input.setInputFiles("./fixtures/old.pdf");
  await expect(page.getByText("old.pdf")).toBeVisible();

  // Clear selection
  await input.setInputFiles([]);

  // Upload new file
  await input.setInputFiles("./fixtures/new.pdf");
  await expect(page.getByText("new.pdf")).toBeVisible();
  await expect(page.getByText("old.pdf")).toBeHidden();
});
```

### Upload from Buffer

```typescript
test("upload generated file", async ({ page }) => {
  await page.goto("/upload");

  // Create file content dynamically
  const content = "Name,Email\nJohn,john@example.com";

  await page.getByLabel("CSV File").setInputFiles({
    name: "users.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(content),
  });

  await expect(page.getByText("users.csv")).toBeVisible();
});
```

## Drag and Drop

### Drag and Drop Upload

```typescript
test("drag and drop file upload", async ({ page }) => {
  await page.goto("/upload");

  const dropzone = page.getByTestId("dropzone");

  // Create a DataTransfer with the file
  const dataTransfer = await page.evaluateHandle(() => new DataTransfer());

  // Read file and add to DataTransfer
  const buffer = fs.readFileSync("./fixtures/image.png");
  await page.evaluate(
    async ([dataTransfer, data]) => {
      const file = new File([new Uint8Array(data)], "image.png", {
        type: "image/png",
      });
      dataTransfer.items.add(file);
    },
    [dataTransfer, [...buffer]] as const,
  );

  // Dispatch drop event
  await dropzone.dispatchEvent("drop", { dataTransfer });

  await expect(page.getByText("image.png uploaded")).toBeVisible();
});
```

### Simpler Drag and Drop

```typescript
test("drag and drop with setInputFiles", async ({ page }) => {
  await page.goto("/upload");

  // Most dropzones have a hidden file input
  const input = page.locator('input[type="file"]');

  // This works even if the input is hidden
  await input.setInputFiles("./fixtures/document.pdf");

  await expect(page.getByText("document.pdf")).toBeVisible();
});
```

## File Content Verification

### Verify PDF Content

```typescript
import pdf from "pdf-parse";

test("verify PDF content", async ({ page }, testInfo) => {
  await page.goto("/invoice/123");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Invoice" }).click();
  const download = await downloadPromise;

  const path = testInfo.outputPath("invoice.pdf");
  await download.saveAs(path);

  // Parse PDF
  const dataBuffer = fs.readFileSync(path);
  const data = await pdf(dataBuffer);

  expect(data.text).toContain("Invoice #123");
  expect(data.text).toContain("Total: $99.99");
});
```

### Verify Excel Content

```typescript
import XLSX from "xlsx";

test("verify Excel export", async ({ page }, testInfo) => {
  await page.goto("/reports");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export Excel" }).click();
  const download = await downloadPromise;

  const path = testInfo.outputPath("report.xlsx");
  await download.saveAs(path);

  // Parse Excel
  const workbook = XLSX.readFile(path);
  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  const data = XLSX.utils.sheet_to_json(sheet);

  expect(data).toHaveLength(10);
  expect(data[0]).toHaveProperty("Name");
  expect(data[0]).toHaveProperty("Email");
});
```

### Verify JSON Download

```typescript
test("verify JSON export", async ({ page }, testInfo) => {
  await page.goto("/api-data");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON" }).click();
  const download = await downloadPromise;

  const path = testInfo.outputPath("data.json");
  await download.saveAs(path);

  const content = JSON.parse(fs.readFileSync(path, "utf-8"));

  expect(content.users).toHaveLength(5);
  expect(content.exportDate).toBeDefined();
});
```

## Anti-Patterns to Avoid

| Anti-Pattern                          | Problem                         | Solution                                      |
| ------------------------------------- | ------------------------------- | --------------------------------------------- |
| Not waiting for download              | Race condition, test fails      | Always use `waitForEvent("download")`         |
| Hardcoded download paths              | Conflicts in parallel runs      | Use `testInfo.outputPath()`                   |
| Skipping content verification         | Download might be empty/corrupt | Verify file content when possible             |
| Using `force: true` for hidden inputs | May not trigger proper events   | Use `setInputFiles` on hidden inputs directly |

## Related References

- **Fixtures**: See [fixtures-hooks.md](../core/fixtures-hooks.md) for download fixture patterns
- **Debugging**: See [debugging.md](../debugging/debugging.md) for troubleshooting download issues
