# File Upload and Download Testing

> **When to use**: Testing file uploads (single, multiple, drag-and-drop), downloads (content verification, filename, type), upload progress indicators, or file type/size restrictions.

## Table of Contents

1. [Downloading Files](#downloading-files)
2. [Single File Upload](#single-file-upload)
3. [Multiple File Upload](#multiple-file-upload)
4. [Drag-and-Drop Zones](#drag-and-drop-zones)
5. [File Chooser Dialog](#file-chooser-dialog)
6. [Upload Progress and Cancellation](#upload-progress-and-cancellation)
7. [Retry After Failure](#retry-after-failure)
8. [File Type and Size Restrictions](#file-type-and-size-restrictions)
9. [Image Preview](#image-preview)
10. [Authenticated Downloads](#authenticated-downloads)
11. [Tips](#tips)

---

## Downloading Files

### Capturing Downloads and Verifying Content

```typescript
import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

test('verifies downloaded CSV content', async ({ page }) => {
  await page.goto('/exports');

  // Set up download listener BEFORE triggering the download
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: 'transactions.csv' }).click();

  const download = await downloadPromise;
  const savePath = path.join(__dirname, '../tmp', download.suggestedFilename());
  await download.saveAs(savePath);

  const content = fs.readFileSync(savePath, 'utf-8');
  expect(content).toContain('id,amount,date');
  expect(content).toContain('1001,250.00,2025-01-15');

  const rows = content.trim().split('\n');
  expect(rows.length).toBeGreaterThan(1);

  fs.unlinkSync(savePath);
});

test('reads download via stream without disk I/O', async ({ page }) => {
  await page.goto('/exports');

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: 'transactions.csv' }).click();

  const download = await downloadPromise;
  const readable = await download.createReadStream();
  const chunks: Buffer[] = [];

  for await (const chunk of readable!) {
    chunks.push(Buffer.from(chunk));
  }

  const content = Buffer.concat(chunks).toString('utf-8');
  expect(content).toContain('id,amount,date');
});
```

### Verifying Filename and Format

```typescript
test('export filename matches selected format', async ({ page }) => {
  await page.goto('/analytics');

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export PDF' }).click();

  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^analytics-\d{4}-\d{2}-\d{2}\.pdf$/);
});

test('format selector changes output extension', async ({ page }) => {
  await page.goto('/analytics');

  await page.getByLabel('Format').selectOption('csv');
  const csvDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download' }).click();
  expect((await csvDownload).suggestedFilename()).toMatch(/\.csv$/);

  await page.getByLabel('Format').selectOption('xlsx');
  const xlsxDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download' }).click();
  expect((await xlsxDownload).suggestedFilename()).toMatch(/\.xlsx$/);
});
```

### Checking Response Headers

```typescript
test('download response has correct MIME type', async ({ page }) => {
  await page.goto('/analytics');

  const responsePromise = page.waitForResponse('**/api/analytics/export**');
  const downloadPromise = page.waitForEvent('download');

  await page.getByRole('button', { name: 'Export PDF' }).click();

  const response = await responsePromise;
  expect(response.headers()['content-type']).toContain('application/pdf');
  expect(response.headers()['content-disposition']).toContain('attachment');

  await downloadPromise;
});
```

### Handling Download Failures

```typescript
test('shows error when download fails', async ({ page }) => {
  await page.route('**/api/analytics/export**', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Generation failed' }),
    });
  });

  await page.goto('/analytics');
  await page.getByRole('button', { name: 'Export PDF' }).click();

  await expect(page.getByRole('alert')).toContainText(/failed|error/i);
});
```

---

## Single File Upload

### From Fixture File

```typescript
import path from 'path';

test('uploads document from fixture', async ({ page }) => {
  await page.goto('/attachments');

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(path.resolve(__dirname, '../fixtures/invoice.pdf'));

  await expect(page.getByText('invoice.pdf')).toBeVisible();

  await page.getByRole('button', { name: 'Upload' }).click();
  await expect(page.getByRole('alert')).toContainText('uploaded successfully');
  await expect(page.getByRole('link', { name: 'invoice.pdf' })).toBeVisible();
});
```

### From In-Memory Buffer

```typescript
test('uploads in-memory CSV', async ({ page }) => {
  await page.goto('/attachments');

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: 'contacts.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('name,email\nAlice,alice@acme.com\nBob,bob@acme.com'),
  });

  await expect(page.getByText('contacts.csv')).toBeVisible();
  await page.getByRole('button', { name: 'Upload' }).click();
  await expect(page.getByRole('alert')).toContainText('uploaded successfully');
});
```

### Clearing Selection

```typescript
test('clears selected file', async ({ page }) => {
  await page.goto('/attachments');

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: 'draft.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('draft content'),
  });

  await expect(page.getByText('draft.txt')).toBeVisible();

  // Clear via API
  await fileInput.setInputFiles([]);
  await expect(page.getByText('draft.txt')).not.toBeVisible();
});
```

---

## Multiple File Upload

```typescript
test('uploads multiple files at once', async ({ page }) => {
  await page.goto('/attachments');

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles([
    { name: 'doc1.pdf', mimeType: 'application/pdf', buffer: Buffer.from('pdf1') },
    { name: 'doc2.pdf', mimeType: 'application/pdf', buffer: Buffer.from('pdf2') },
    { name: 'doc3.pdf', mimeType: 'application/pdf', buffer: Buffer.from('pdf3') },
  ]);

  await expect(page.getByText('doc1.pdf')).toBeVisible();
  await expect(page.getByText('doc2.pdf')).toBeVisible();
  await expect(page.getByText('doc3.pdf')).toBeVisible();
  await expect(page.getByText('3 files selected')).toBeVisible();

  await page.getByRole('button', { name: 'Upload all' }).click();
  await expect(page.getByRole('alert')).toContainText('3 files uploaded');
});

test('removes one file from selection', async ({ page }) => {
  await page.goto('/attachments');

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles([
    { name: 'keep.txt', mimeType: 'text/plain', buffer: Buffer.from('keep') },
    { name: 'discard.txt', mimeType: 'text/plain', buffer: Buffer.from('discard') },
  ]);

  const discardRow = page.getByText('discard.txt').locator('..');
  await discardRow.getByRole('button', { name: /remove|delete|×/i }).click();

  await expect(page.getByText('discard.txt')).not.toBeVisible();
  await expect(page.getByText('keep.txt')).toBeVisible();
});
```

---

## Drag-and-Drop Zones

Drop zones always have an underlying `input[type="file"]`—target it directly instead of simulating OS-level drag events.

```typescript
test('uploads via drop zone', async ({ page }) => {
  await page.goto('/attachments');

  const dropZone = page.locator('[data-testid="drop-zone"]');
  await expect(dropZone).toContainText(/drag.*here|drop.*files/i);

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: 'dropped.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('pdf-content'),
  });

  await expect(dropZone.getByText('dropped.pdf')).toBeVisible();
  await page.getByRole('button', { name: 'Upload' }).click();
  await expect(page.getByRole('alert')).toContainText('uploaded successfully');
});

test('shows visual feedback on drag-over', async ({ page }) => {
  await page.goto('/attachments');

  const dropZone = page.locator('[data-testid="drop-zone"]');

  await dropZone.dispatchEvent('dragenter', {
    dataTransfer: { types: ['Files'], files: [] },
  });

  await expect(dropZone).toHaveClass(/active|highlight|drag-over/);
  await expect(dropZone).toContainText(/release|drop now/i);

  await dropZone.dispatchEvent('dragleave');
  await expect(dropZone).not.toHaveClass(/active|highlight|drag-over/);
});
```

---

## File Chooser Dialog

```typescript
test('uploads via native file chooser', async ({ page }) => {
  await page.goto('/attachments');

  const fileChooserPromise = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Choose file' }).click();

  const fileChooser = await fileChooserPromise;
  expect(fileChooser.isMultiple()).toBe(false);

  await fileChooser.setFiles({
    name: 'selected.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('pdf-content'),
  });

  await expect(page.getByText('selected.pdf')).toBeVisible();
});
```

---

## Upload Progress and Cancellation

```typescript
test('displays upload progress for large file', async ({ page }) => {
  await page.goto('/attachments');

  const fileInput = page.locator('input[type="file"]');
  const largeBuffer = Buffer.alloc(5 * 1024 * 1024, 'x');

  await fileInput.setInputFiles({
    name: 'dataset.bin',
    mimeType: 'application/octet-stream',
    buffer: largeBuffer,
  });

  await page.getByRole('button', { name: 'Upload' }).click();

  const progressBar = page.getByRole('progressbar');
  await expect(progressBar).toBeVisible();

  await expect(async () => {
    const value = await progressBar.getAttribute('aria-valuenow');
    expect(Number(value)).toBeGreaterThan(0);
  }).toPass({ timeout: 10000 });

  await expect(progressBar).not.toBeVisible({ timeout: 60000 });
  await expect(page.getByRole('alert')).toContainText('uploaded successfully');
});

test('cancels in-progress upload', async ({ page }) => {
  await page.route('**/api/attachments/upload', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 10000));
    await route.continue();
  });

  await page.goto('/attachments');

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: 'large.bin',
    mimeType: 'application/octet-stream',
    buffer: Buffer.alloc(5 * 1024 * 1024, 'x'),
  });

  await page.getByRole('button', { name: 'Upload' }).click();
  await expect(page.getByRole('progressbar')).toBeVisible();

  await page.getByRole('button', { name: 'Cancel upload' }).click();

  await expect(page.getByRole('progressbar')).not.toBeVisible();
  await expect(page.getByText(/cancelled|aborted/i)).toBeVisible();
  await expect(page.getByRole('link', { name: 'large.bin' })).not.toBeVisible();
});
```

---

## Retry After Failure

```typescript
test('retries failed upload', async ({ page }) => {
  let attempt = 0;

  await page.route('**/api/attachments/upload', async (route) => {
    attempt++;
    if (attempt === 1) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Server error' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'abc', name: 'data.csv' }),
      });
    }
  });

  await page.goto('/attachments');

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: 'data.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('col1,col2\nval1,val2'),
  });

  await page.getByRole('button', { name: 'Upload' }).click();
  await expect(page.getByText(/upload failed|error/i)).toBeVisible();

  await page.getByRole('button', { name: /retry/i }).click();
  await expect(page.getByRole('alert')).toContainText('uploaded successfully');
  expect(attempt).toBe(2);
});
```

---

## File Type and Size Restrictions

### Validating Allowed Types

```typescript
test('accepts allowed file types', async ({ page }) => {
  await page.goto('/attachments');

  const fileInput = page.locator('input[type="file"]');
  await expect(fileInput).toHaveAttribute('accept', /\.pdf|\.doc|\.docx|\.txt/);

  await fileInput.setInputFiles({
    name: 'report.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('pdf-content'),
  });

  await expect(page.getByText('report.pdf')).toBeVisible();
  await expect(page.getByText(/not allowed|invalid/i)).not.toBeVisible();
});

test('rejects disallowed file types', async ({ page }) => {
  await page.goto('/attachments');

  const fileInput = page.locator('input[type="file"]');
  // setInputFiles bypasses the accept attribute—tests JavaScript validation
  await fileInput.setInputFiles({
    name: 'malware.exe',
    mimeType: 'application/x-msdownload',
    buffer: Buffer.from('exe-content'),
  });

  await expect(page.getByRole('alert')).toContainText(
    /not allowed|unsupported file type|only .pdf, .doc/i
  );
  await expect(page.getByText('malware.exe')).not.toBeVisible();
});
```

### Enforcing Size Limits

```typescript
test('rejects oversized file', async ({ page }) => {
  await page.goto('/attachments');

  const fileInput = page.locator('input[type="file"]');
  const oversizedBuffer = Buffer.alloc(11 * 1024 * 1024, 'x');

  await fileInput.setInputFiles({
    name: 'huge.pdf',
    mimeType: 'application/pdf',
    buffer: oversizedBuffer,
  });

  await expect(page.getByRole('alert')).toContainText(/file.*too large|exceeds.*10 ?MB/i);
  await expect(page.getByText('huge.pdf')).not.toBeVisible();
});
```

### Enforcing File Count Limits

```typescript
test('rejects too many files', async ({ page }) => {
  await page.goto('/attachments');

  const fileInput = page.locator('input[type="file"]');
  const files = Array.from({ length: 6 }, (_, i) => ({
    name: `file-${i + 1}.txt`,
    mimeType: 'text/plain' as const,
    buffer: Buffer.from(`content ${i + 1}`),
  }));

  await fileInput.setInputFiles(files);

  await expect(page.getByRole('alert')).toContainText(/maximum.*5 files|too many files/i);
});
```

### Validating Image Dimensions

```typescript
test('rejects image below minimum dimensions', async ({ page }) => {
  await page.goto('/profile/avatar');

  const fileInput = page.locator('input[type="file"]');
  // Minimal 1x1 PNG
  const tinyPng = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
    'base64'
  );

  await fileInput.setInputFiles({
    name: 'tiny.png',
    mimeType: 'image/png',
    buffer: tinyPng,
  });

  await expect(page.getByRole('alert')).toContainText(/minimum.*dimensions|too small/i);
});
```

---

## Image Preview

```typescript
test('shows image preview after selection', async ({ page }) => {
  await page.goto('/profile/avatar');

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(path.resolve(__dirname, '../fixtures/photo.jpg'));

  const preview = page.getByRole('img', { name: /preview|avatar/i });
  await expect(preview).toBeVisible();

  const src = await preview.getAttribute('src');
  expect(src).toMatch(/^(blob:|data:image)/);
});
```

---

## Authenticated Downloads

```typescript
test('downloads file requiring authentication', async ({ page, request }) => {
  await page.goto('/attachments');

  // Browser download works because cookies are sent
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: 'confidential.pdf' }).click();

  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('confidential.pdf');

  // Verify via API request (carries auth context)
  const response = await request.get('/api/attachments/456/download');
  expect(response.ok()).toBeTruthy();
  expect(response.headers()['content-type']).toContain('application/pdf');
});
```

---

## Tips

1. **Use `setInputFiles` for uploads**. Even drag-and-drop zones have an underlying `input[type="file"]`. Target it directly instead of simulating OS-level drag events.

2. **Prefer in-memory buffers**. Creating files with `Buffer.from()` keeps tests self-contained. Use fixture files only when you need real content (e.g., a valid PDF your app parses).

3. **Set up download listener before clicking**. Call `page.waitForEvent('download')` before the click that triggers the download—otherwise you may miss the event.

4. **Use `createReadStream()` for content verification**. Reading directly from the stream avoids disk I/O and cleanup of temporary files.

5. **Test both `accept` attribute and JavaScript validation**. The HTML `accept` attribute only filters the OS file dialog. `setInputFiles()` bypasses it, which is exactly what you need to test your app's JavaScript validation.
