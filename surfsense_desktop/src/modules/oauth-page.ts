import http from 'node:http';

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderOAuthPage(title: string, message: string): string {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(title)}</title>
    <style>
      :root {
        color-scheme: dark;
      }
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #303030;
        background: oklch(0.24 0 0);
        color: #fafafa;
      }
      main {
        width: min(420px, calc(100vw - 32px));
        text-align: center;
      }
      h1 {
        margin: 0 0 12px;
        font-size: 24px;
        line-height: 1.2;
        letter-spacing: -0.02em;
      }
      p {
        margin: 0;
        color: #d4d4d4;
        line-height: 1.5;
      }
    </style>
  </head>
  <body>
    <main>
      <h1>${escapeHtml(title)}</h1>
      <p>${escapeHtml(message)}</p>
    </main>
  </body>
</html>`;
}

export function writeOAuthPage(
  res: http.ServerResponse,
  statusCode: number,
  title: string,
  message: string,
  _tone?: 'success' | 'error' | 'neutral',
): void {
  res
    .writeHead(statusCode, { 'content-type': 'text/html; charset=utf-8' })
    .end(renderOAuthPage(title, message));
}
