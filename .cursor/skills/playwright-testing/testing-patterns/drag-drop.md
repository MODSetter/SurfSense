# Drag and Drop Testing

## Table of Contents

1. [Kanban Board (Cross-Column Movement)](#kanban-board-cross-column-movement)
2. [Sortable Lists (Reordering)](#sortable-lists-reordering)
3. [Native HTML5 Drag and Drop](#native-html5-drag-and-drop)
4. [File Drop Zone](#file-drop-zone)
5. [Canvas Coordinate-Based Dragging](#canvas-coordinate-based-dragging)
6. [Custom Drag Preview](#custom-drag-preview)
7. [Variations](#variations)
8. [Tips](#tips)

> **When to use**: Testing drag-and-drop interactions — sortable lists, kanban boards, file drop zones, or repositionable elements.

---

## Kanban Board (Cross-Column Movement)

```typescript
import { test, expect } from '@playwright/test';

test('moves card between columns', async ({ page }) => {
  await page.goto('/board');

  const backlog = page.locator('[data-column="backlog"]');
  const active = page.locator('[data-column="active"]');

  const ticket = backlog.getByText('Update API docs');
  await expect(ticket).toBeVisible();

  const backlogCountBefore = await backlog.getByRole('article').count();
  const activeCountBefore = await active.getByRole('article').count();

  await ticket.dragTo(active);

  await expect(active.getByText('Update API docs')).toBeVisible();
  await expect(backlog.getByText('Update API docs')).not.toBeVisible();

  await expect(backlog.getByRole('article')).toHaveCount(backlogCountBefore - 1);
  await expect(active.getByRole('article')).toHaveCount(activeCountBefore + 1);
});

test('progresses card through workflow stages', async ({ page }) => {
  await page.goto('/board');

  const cols = {
    backlog: page.locator('[data-column="backlog"]'),
    active: page.locator('[data-column="active"]'),
    review: page.locator('[data-column="review"]'),
    complete: page.locator('[data-column="complete"]'),
  };

  await cols.backlog.getByText('Update API docs').dragTo(cols.active);
  await expect(cols.active.getByText('Update API docs')).toBeVisible();

  await cols.active.getByText('Update API docs').dragTo(cols.review);
  await expect(cols.review.getByText('Update API docs')).toBeVisible();

  await cols.review.getByText('Update API docs').dragTo(cols.complete);
  await expect(cols.complete.getByText('Update API docs')).toBeVisible();

  await expect(cols.backlog.getByText('Update API docs')).not.toBeVisible();
  await expect(cols.active.getByText('Update API docs')).not.toBeVisible();
  await expect(cols.review.getByText('Update API docs')).not.toBeVisible();
});

test('reorders cards within same column', async ({ page }) => {
  await page.goto('/board');

  const backlog = page.locator('[data-column="backlog"]');

  const itemX = backlog.getByRole('article').filter({ hasText: 'Item X' });
  const itemZ = backlog.getByRole('article').filter({ hasText: 'Item Z' });

  await itemZ.dragTo(itemX);

  const cards = await backlog.getByRole('article').allTextContents();
  expect(cards.indexOf('Item Z')).toBeLessThan(cards.indexOf('Item X'));
});

test('verifies drag persists via API', async ({ page }) => {
  await page.goto('/board');

  const backlog = page.locator('[data-column="backlog"]');
  const active = page.locator('[data-column="active"]');

  const responsePromise = page.waitForResponse(
    (r) => r.url().includes('/api/tickets') && r.request().method() === 'PATCH'
  );

  await backlog.getByText('Update API docs').dragTo(active);

  const response = await responsePromise;
  expect(response.status()).toBe(200);

  const body = await response.json();
  expect(body.column).toBe('active');

  await page.reload();
  await expect(active.getByText('Update API docs')).toBeVisible();
});
```

---

## Sortable Lists (Reordering)

```typescript
import { test, expect } from '@playwright/test';

test('reorders list items', async ({ page }) => {
  await page.goto('/priorities');

  const list = page.getByRole('list', { name: 'Priority list' });

  const initial = await list.getByRole('listitem').allTextContents();
  expect(initial[0]).toContain('Priority A');
  expect(initial[1]).toContain('Priority B');
  expect(initial[2]).toContain('Priority C');

  const priorityC = list.getByRole('listitem').filter({ hasText: 'Priority C' });
  const priorityA = list.getByRole('listitem').filter({ hasText: 'Priority A' });

  await priorityC.dragTo(priorityA);

  const reordered = await list.getByRole('listitem').allTextContents();
  expect(reordered[0]).toContain('Priority C');
  expect(reordered[1]).toContain('Priority A');
  expect(reordered[2]).toContain('Priority B');
});

test('reorders via drag handle', async ({ page }) => {
  await page.goto('/priorities');

  const list = page.getByRole('list', { name: 'Priority list' });

  const handle = list
    .getByRole('listitem')
    .filter({ hasText: 'Priority C' })
    .getByRole('button', { name: /drag|reorder|grip/i });

  const target = list.getByRole('listitem').filter({ hasText: 'Priority A' });

  await handle.dragTo(target);

  const items = await list.getByRole('listitem').allTextContents();
  expect(items[0]).toContain('Priority C');
});

test('reorder persists after reload', async ({ page }) => {
  await page.goto('/priorities');

  const list = page.getByRole('list', { name: 'Priority list' });

  const priorityC = list.getByRole('listitem').filter({ hasText: 'Priority C' });
  const priorityA = list.getByRole('listitem').filter({ hasText: 'Priority A' });

  await priorityC.dragTo(priorityA);

  await page.waitForResponse((response) =>
    response.url().includes('/api/priorities/reorder') && response.status() === 200
  );

  await page.reload();

  const items = await list.getByRole('listitem').allTextContents();
  expect(items[0]).toContain('Priority C');
  expect(items[1]).toContain('Priority A');
  expect(items[2]).toContain('Priority B');
});
```

### Incremental Mouse Movement for Custom Libraries

Some drag libraries (react-beautiful-dnd, dnd-kit) require incremental mouse movements:

```typescript
test('reorders with incremental mouse movements', async ({ page }) => {
  await page.goto('/priorities');

  const list = page.getByRole('list', { name: 'Priority list' });
  const source = list.getByRole('listitem').filter({ hasText: 'Priority C' });
  const target = list.getByRole('listitem').filter({ hasText: 'Priority A' });

  const sourceBox = await source.boundingBox();
  const targetBox = await target.boundingBox();

  await source.hover();
  await page.mouse.down();

  const steps = 10;
  for (let i = 1; i <= steps; i++) {
    await page.mouse.move(
      sourceBox!.x + sourceBox!.width / 2,
      sourceBox!.y + (targetBox!.y - sourceBox!.y) * (i / steps),
      { steps: 1 }
    );
  }

  await page.mouse.up();

  const items = await list.getByRole('listitem').allTextContents();
  expect(items[0]).toContain('Priority C');
});
```

---

## Native HTML5 Drag and Drop

```typescript
import { test, expect } from '@playwright/test';

test('drags item to drop zone', async ({ page }) => {
  await page.goto('/drag-example');

  const source = page.getByText('Movable Element');
  const dropArea = page.locator('#target-zone');

  await expect(source).toBeVisible();
  await expect(dropArea).not.toContainText('Movable Element');

  await source.dragTo(dropArea);

  await expect(dropArea).toContainText('Movable Element');
});

test('drags between zones', async ({ page }) => {
  await page.goto('/drag-example');

  const item = page.locator('[data-testid="element-1"]');
  const areaA = page.locator('[data-testid="area-a"]');
  const areaB = page.locator('[data-testid="area-b"]');

  await expect(areaA).toContainText('Element 1');

  await item.dragTo(areaB);

  await expect(areaB).toContainText('Element 1');
  await expect(areaA).not.toContainText('Element 1');

  await areaB.getByText('Element 1').dragTo(areaA);

  await expect(areaA).toContainText('Element 1');
  await expect(areaB).not.toContainText('Element 1');
});

test('verifies drag visual feedback', async ({ page }) => {
  await page.goto('/drag-example');

  const source = page.getByText('Movable Element');
  const dropArea = page.locator('#target-zone');

  await source.hover();
  await page.mouse.down();

  const dropBox = await dropArea.boundingBox();
  await page.mouse.move(dropBox!.x + dropBox!.width / 2, dropBox!.y + dropBox!.height / 2);

  await expect(dropArea).toHaveClass(/drag-over|highlight/);

  await page.mouse.up();

  await expect(dropArea).not.toHaveClass(/drag-over|highlight/);
  await expect(dropArea).toContainText('Movable Element');
});
```

---

## File Drop Zone

```typescript
import { test, expect } from '@playwright/test';
import path from 'path';

test('uploads file via drop zone', async ({ page }) => {
  await page.goto('/upload');

  const dropZone = page.locator('[data-testid="file-drop-zone"]');

  await expect(dropZone).toContainText('Drag files here');

  const fileInput = page.locator('input[type="file"]');

  await fileInput.setInputFiles(path.resolve(__dirname, '../fixtures/report.pdf'));

  await expect(page.getByText('report.pdf')).toBeVisible();
  await expect(page.getByText(/\d+ KB/)).toBeVisible();
});

test('simulates drag-over visual feedback', async ({ page }) => {
  await page.goto('/upload');

  const dropZone = page.locator('[data-testid="file-drop-zone"]');

  await dropZone.dispatchEvent('dragenter', {
    dataTransfer: { types: ['Files'] },
  });

  await expect(dropZone).toHaveClass(/drag-active|drop-highlight/);
  await expect(dropZone).toContainText(/drop.*here|release.*upload/i);

  await dropZone.dispatchEvent('dragleave');

  await expect(dropZone).not.toHaveClass(/drag-active|drop-highlight/);
});

test('rejects invalid file types', async ({ page }) => {
  await page.goto('/upload');

  const fileInput = page.locator('input[type="file"]');

  await fileInput.setInputFiles({
    name: 'script.exe',
    mimeType: 'application/x-msdownload',
    buffer: Buffer.from('fake-content'),
  });

  await expect(page.getByRole('alert')).toContainText(/not allowed|invalid file type/i);
  await expect(page.getByText('script.exe')).not.toBeVisible();
});
```

---

## Canvas Coordinate-Based Dragging

```typescript
import { test, expect } from '@playwright/test';

test('drags element to specific coordinates', async ({ page }) => {
  await page.goto('/design-tool');

  const canvas = page.locator('#editor-canvas');
  const shape = page.locator('[data-testid="shape-1"]');

  const canvasBox = await canvas.boundingBox();
  const targetX = canvasBox!.x + 300;
  const targetY = canvasBox!.y + 200;

  await shape.hover();
  await page.mouse.down();
  await page.mouse.move(targetX, targetY, { steps: 10 });
  await page.mouse.up();

  const newBox = await shape.boundingBox();
  expect(newBox!.x).toBeCloseTo(targetX - newBox!.width / 2, -1);
  expect(newBox!.y).toBeCloseTo(targetY - newBox!.height / 2, -1);
});

test('snaps element to grid', async ({ page }) => {
  await page.goto('/design-tool');

  const shape = page.locator('[data-testid="shape-1"]');
  const canvas = page.locator('#editor-canvas');

  const canvasBox = await canvas.boundingBox();

  await shape.hover();
  await page.mouse.down();
  await page.mouse.move(canvasBox!.x + 147, canvasBox!.y + 83, { steps: 10 });
  await page.mouse.up();

  const snappedBox = await shape.boundingBox();
  expect(snappedBox!.x % 20).toBeCloseTo(0, 0);
  expect(snappedBox!.y % 20).toBeCloseTo(0, 0);
});

test('constrains drag within boundaries', async ({ page }) => {
  await page.goto('/design-tool');

  const shape = page.locator('[data-testid="bounded-shape"]');
  const container = page.locator('#bounds-container');

  const containerBox = await container.boundingBox();

  await shape.hover();
  await page.mouse.down();
  await page.mouse.move(containerBox!.x + containerBox!.width + 500, containerBox!.y - 200, {
    steps: 10,
  });
  await page.mouse.up();

  const shapeBox = await shape.boundingBox();

  expect(shapeBox!.x).toBeGreaterThanOrEqual(containerBox!.x);
  expect(shapeBox!.y).toBeGreaterThanOrEqual(containerBox!.y);
  expect(shapeBox!.x + shapeBox!.width).toBeLessThanOrEqual(
    containerBox!.x + containerBox!.width
  );
  expect(shapeBox!.y + shapeBox!.height).toBeLessThanOrEqual(
    containerBox!.y + containerBox!.height
  );
});

test('resizes element via handle', async ({ page }) => {
  await page.goto('/design-tool');

  const shape = page.locator('[data-testid="shape-1"]');
  await shape.click();

  const resizeHandle = shape.locator('.resize-handle-se');
  const handleBox = await resizeHandle.boundingBox();

  const initialBox = await shape.boundingBox();

  await resizeHandle.hover();
  await page.mouse.down();
  await page.mouse.move(handleBox!.x + 100, handleBox!.y + 80, { steps: 5 });
  await page.mouse.up();

  const newBox = await shape.boundingBox();
  expect(newBox!.width).toBeCloseTo(initialBox!.width + 100, -1);
  expect(newBox!.height).toBeCloseTo(initialBox!.height + 80, -1);
});
```

---

## Custom Drag Preview

```typescript
import { test, expect } from '@playwright/test';

test('shows custom drag preview', async ({ page }) => {
  await page.goto('/board');

  const card = page.locator('[data-testid="ticket-1"]');
  const targetCol = page.locator('[data-column="active"]');

  const cardBox = await card.boundingBox();
  const targetBox = await targetCol.boundingBox();

  await card.hover();
  await page.mouse.down();

  const midX = (cardBox!.x + targetBox!.x) / 2;
  const midY = (cardBox!.y + targetBox!.y) / 2;
  await page.mouse.move(midX, midY, { steps: 5 });

  await expect(page.locator('.drag-preview')).toBeVisible();
  await expect(card).toHaveClass(/dragging|placeholder/);

  await page.mouse.move(
    targetBox!.x + targetBox!.width / 2,
    targetBox!.y + targetBox!.height / 2,
    { steps: 5 }
  );
  await page.mouse.up();

  await expect(page.locator('.drag-preview')).not.toBeVisible();
});

test('multi-select drag shows item count', async ({ page }) => {
  await page.goto('/board');

  await page.locator('[data-testid="ticket-1"]').click();
  await page.locator('[data-testid="ticket-2"]').click({ modifiers: ['Shift'] });
  await page.locator('[data-testid="ticket-3"]').click({ modifiers: ['Shift'] });

  const card = page.locator('[data-testid="ticket-1"]');
  const targetCol = page.locator('[data-column="complete"]');

  await card.hover();
  await page.mouse.down();

  const targetBox = await targetCol.boundingBox();
  await page.mouse.move(targetBox!.x + 50, targetBox!.y + 50, { steps: 5 });

  await expect(page.locator('.drag-preview')).toContainText('3 items');

  await page.mouse.up();

  await expect(targetCol.locator('[data-testid="ticket-1"]')).toBeVisible();
  await expect(targetCol.locator('[data-testid="ticket-2"]')).toBeVisible();
  await expect(targetCol.locator('[data-testid="ticket-3"]')).toBeVisible();
});
```

---

## Variations

### Keyboard-Based Reordering

```typescript
test('reorders using keyboard', async ({ page }) => {
  await page.goto('/priorities');

  const list = page.getByRole('list', { name: 'Priority list' });
  const priorityC = list.getByRole('listitem').filter({ hasText: 'Priority C' });

  await priorityC.focus();
  await page.keyboard.press('Space');

  await page.keyboard.press('ArrowUp');
  await page.keyboard.press('ArrowUp');

  await page.keyboard.press('Space');

  const items = await list.getByRole('listitem').allTextContents();
  expect(items[0]).toContain('Priority C');
});
```

### Cross-Frame Dragging

```typescript
test('drags between main page and iframe', async ({ page }) => {
  await page.goto('/composer');

  const sourceWidget = page.getByText('Component A');
  const iframe = page.frameLocator('#preview-frame');
  const iframeElement = page.locator('#preview-frame');

  const sourceBox = await sourceWidget.boundingBox();
  const iframeBox = await iframeElement.boundingBox();

  const targetX = iframeBox!.x + 100;
  const targetY = iframeBox!.y + 100;

  await sourceWidget.hover();
  await page.mouse.down();
  await page.mouse.move(targetX, targetY, { steps: 20 });
  await page.mouse.up();

  await expect(iframe.getByText('Component A')).toBeVisible();
});
```

### Touch-Based Drag on Mobile

```typescript
test('drags via touch events', async ({ page }) => {
  await page.goto('/priorities');

  const list = page.getByRole('list', { name: 'Priority list' });
  const source = list.getByRole('listitem').filter({ hasText: 'Priority C' });
  const target = list.getByRole('listitem').filter({ hasText: 'Priority A' });

  const sourceBox = await source.boundingBox();
  const targetBox = await target.boundingBox();

  await source.dispatchEvent('touchstart', {
    touches: [{ clientX: sourceBox!.x + 10, clientY: sourceBox!.y + 10 }],
  });

  for (let i = 1; i <= 5; i++) {
    const y = sourceBox!.y + (targetBox!.y - sourceBox!.y) * (i / 5);
    await source.dispatchEvent('touchmove', {
      touches: [{ clientX: sourceBox!.x + 10, clientY: y }],
    });
  }

  await source.dispatchEvent('touchend');

  const items = await list.getByRole('listitem').allTextContents();
  expect(items[0]).toContain('Priority C');
});
```

---

## Tips

1. **Start with `dragTo()`, fall back to manual mouse events**. Playwright's `dragTo()` handles most HTML5 drag-and-drop. Use `page.mouse.down()` / `move()` / `up()` only for custom libraries (react-beautiful-dnd, dnd-kit, SortableJS) that need specific event sequences.

2. **Add intermediate mouse steps for drag libraries**. Libraries like `react-beautiful-dnd` require multiple `mousemove` events. Use `{ steps: 10 }` or a manual loop — a single jump often fails silently.

3. **Assert final state, not just the drop event**. Verify DOM reflects the change — item order, column contents, position coordinates. Visual feedback during drag is secondary to the persisted state.

4. **Use `boundingBox()` for coordinate assertions**. For canvas editors or position-sensitive drops, capture bounding box after the operation and compare with `toBeCloseTo()` for tolerance.

5. **Test undo after drag operations**. If your app supports Ctrl+Z, verify the drag is reversible — this catches state management bugs.
