import assert from "node:assert/strict"
import http from "node:http"
import type { AddressInfo } from "node:net"
import test from "node:test"

import { serveDocxSnapshots, type PrintSnapshot } from "./serve-snapshots.ts"

const ROUTES = "/agent/previews/docx-snapshots"
// The key Electron made at launch and handed to the API.
const KEY = "snapshot-key"

type Received = { method: string; path: string; type: string; body: Buffer }

/**
 * The API's snapshot routes: hands out `waiting` once each and records what
 * comes back. Like the API, it refuses a call without the launch's key.
 */
async function fakeApi(
  waiting: { id: string; file_url: string; format?: string; pages?: string }[],
  options: { port?: number; pdfStatus?: number; unansweredPolls?: number } = {},
) {
  const { port = 0, pdfStatus = 204 } = options
  let unansweredPolls = options.unansweredPolls ?? 0
  const received: Received[] = []
  const server = http.createServer((req, res) => {
    const chunks: Buffer[] = []
    req.on("data", (chunk: Buffer) => chunks.push(chunk))
    req.on("end", () => {
      if (req.headers.authorization !== `Bearer ${KEY}`) return res.writeHead(401).end()
      received.push({
        method: req.method ?? "",
        path: req.url ?? "",
        type: req.headers["content-type"] ?? "",
        body: Buffer.concat(chunks),
      })
      if (req.method === "GET" && req.url === `${ROUTES}/next`) {
        // A wedged API: the connection stays open and nothing comes back.
        if (unansweredPolls > 0) {
          unansweredPolls -= 1
          return
        }
        const next = waiting.shift()
        if (!next) return res.writeHead(204).end()
        res.writeHead(200, { "content-type": "application/json" })
        return res.end(JSON.stringify(next))
      }
      if (req.method === "POST" && req.url?.endsWith("/pdf")) {
        return res.writeHead(pdfStatus).end()
      }
      res.writeHead(204).end()
    })
  })
  await new Promise<void>((resolve) => server.listen(port, "127.0.0.1", resolve))
  const bound = (server.address() as AddressInfo).port
  return {
    url: `http://127.0.0.1:${bound}`,
    received,
    answers: () => received.filter((r) => r.method === "POST"),
    close: () =>
      new Promise<void>((resolve) => {
        server.closeAllConnections()
        server.close(() => resolve())
      }),
  }
}

async function until(condition: () => boolean, ms = 3000): Promise<void> {
  const deadline = Date.now() + ms
  while (!condition()) {
    if (Date.now() > deadline) throw new Error("condition never held")
    await new Promise((resolve) => setTimeout(resolve, 5))
  }
}

test("with nothing waiting it keeps polling and prints nothing", async () => {
  const api = await fakeApi([])
  let printed = 0
  const stop = serveDocxSnapshots({
    apiUrl: api.url,
    key: KEY,
    print: async () => {
      printed += 1
      return new Uint8Array()
    },
    pollMs: 5,
  })

  await until(() => api.received.length >= 3)
  stop()
  await api.close()

  assert.equal(printed, 0)
  assert.ok(api.received.every((r) => r.method === "GET"))
})

test("a waiting document is printed from its file URL and the PDF posted back", async () => {
  const api = await fakeApi([{ id: "req-1", file_url: "/artifacts/12/files/primary" }])
  const printedUrls: string[] = []
  const print: PrintSnapshot = async ({ fileUrl }) => {
    printedUrls.push(fileUrl)
    return new TextEncoder().encode("%PDF-1.7 two pages")
  }
  const stop = serveDocxSnapshots({ apiUrl: api.url, key: KEY, print, pollMs: 5 })

  await until(() => api.answers().length === 1)
  stop()
  await api.close()

  assert.deepEqual(printedUrls, [`${api.url}/artifacts/12/files/primary`])
  const [answer] = api.answers()
  assert.equal(answer.path, `${ROUTES}/req-1/pdf`)
  assert.equal(answer.type, "application/pdf")
  assert.equal(answer.body.toString(), "%PDF-1.7 two pages")
})

test("each request is printed as the format and pages it names", async () => {
  const api = await fakeApi([
    { id: "deck", file_url: "/artifacts/7/files/primary", format: "pptx", pages: "1-4" },
    {
      id: "source",
      file_url: `${ROUTES}/source/file`,
      format: "docx",
      pages: "2,5",
    },
    // An API from before decks: every request was a Word file's first pages.
    { id: "older", file_url: "/artifacts/9/files/primary" },
  ])
  const printed: { fileUrl: string; format: string; pages: string }[] = []
  const stop = serveDocxSnapshots({
    apiUrl: api.url,
    key: KEY,
    print: async (file) => {
      printed.push(file)
      return new TextEncoder().encode("%PDF-1.7")
    },
    pollMs: 5,
  })

  await until(() => api.answers().length === 3)
  stop()
  await api.close()

  assert.deepEqual(
    printed.sort((a, b) => a.fileUrl.localeCompare(b.fileUrl)),
    [
      { fileUrl: `${api.url}${ROUTES}/source/file`, format: "docx", pages: "2,5" },
      { fileUrl: `${api.url}/artifacts/7/files/primary`, format: "pptx", pages: "1-4" },
      { fileUrl: `${api.url}/artifacts/9/files/primary`, format: "docx", pages: "1-4" },
    ],
  )
})

test("a format the app cannot print is reported as the request's failure", async () => {
  const api = await fakeApi([
    { id: "book", file_url: "/artifacts/4/files/primary", format: "xlsx" },
  ])
  let printed = 0
  const stop = serveDocxSnapshots({
    apiUrl: api.url,
    key: KEY,
    print: async () => {
      printed += 1
      return new TextEncoder().encode("%PDF-1.7")
    },
    pollMs: 5,
  })

  await until(() => api.answers().length === 1)
  stop()
  await api.close()

  assert.equal(printed, 0)
  const [answer] = api.answers()
  assert.equal(answer.path, `${ROUTES}/book/failure`)
  assert.deepEqual(JSON.parse(answer.body.toString()), {
    reason: "the desktop app cannot print a xlsx file",
  })
})

test("pages that are not a page range are reported as the request's failure", async () => {
  const api = await fakeApi([
    { id: "odd", file_url: "/artifacts/4/files/primary", format: "docx", pages: "all of them" },
  ])
  let printed = 0
  const stop = serveDocxSnapshots({
    apiUrl: api.url,
    key: KEY,
    print: async () => {
      printed += 1
      return new TextEncoder().encode("%PDF-1.7")
    },
    pollMs: 5,
  })

  await until(() => api.answers().length === 1)
  stop()
  await api.close()

  assert.equal(printed, 0)
  assert.deepEqual(JSON.parse(api.answers()[0].body.toString()), {
    reason: "the desktop app cannot print pages \"all of them\"",
  })
})

test("a print that throws is reported as the request's failure", async () => {
  const api = await fakeApi([{ id: "req-2", file_url: "/artifacts/3/files/primary" }])
  const stop = serveDocxSnapshots({
    apiUrl: api.url,
    key: KEY,
    print: async () => {
      throw new Error("docx-preview could not read the file")
    },
    pollMs: 5,
  })

  await until(() => api.answers().length === 1)
  stop()
  await api.close()

  const [answer] = api.answers()
  assert.equal(answer.path, `${ROUTES}/req-2/failure`)
  assert.equal(answer.type, "application/json")
  assert.deepEqual(JSON.parse(answer.body.toString()), {
    reason: "docx-preview could not read the file",
  })
})

test("a print past its time box is aborted and reported, so the API stops waiting", async () => {
  const api = await fakeApi([{ id: "req-3", file_url: "/artifacts/3/files/primary" }])
  let aborted = false
  const stop = serveDocxSnapshots({
    apiUrl: api.url,
    key: KEY,
    // Never settles, as a window torn down mid-print may not: the poller moves on anyway.
    print: (_file, signal) => {
      signal.addEventListener("abort", () => {
        aborted = true
      })
      return new Promise(() => {})
    },
    pollMs: 5,
    printMs: 50,
  })

  await until(() => api.answers().length === 1)
  stop()
  await api.close()

  assert.ok(aborted)
  const [answer] = api.answers()
  assert.equal(answer.path, `${ROUTES}/req-3/failure`)
  assert.deepEqual(JSON.parse(answer.body.toString()), {
    reason: "the document did not lay out and print within 0.05 s",
  })
})

test("a reason too long for the API is cut to its 500 characters", async () => {
  const api = await fakeApi([{ id: "req-4", file_url: "/artifacts/3/files/primary" }])
  const stop = serveDocxSnapshots({
    apiUrl: api.url,
    key: KEY,
    print: async () => {
      throw new Error("x".repeat(2000))
    },
    pollMs: 5,
  })

  await until(() => api.answers().length === 1)
  stop()
  await api.close()

  const { reason } = JSON.parse(api.answers()[0].body.toString()) as { reason: string }
  assert.equal(reason.length, 500)
})

test("an API that is down is polled again until it answers", async () => {
  const down = await fakeApi([])
  const port = Number(new URL(down.url).port)
  await down.close()
  const stop = serveDocxSnapshots({
    apiUrl: down.url,
    key: KEY,
    print: async () => new TextEncoder().encode("%PDF-1.7"),
    pollMs: 5,
  })
  await new Promise((resolve) => setTimeout(resolve, 50))

  const restarted = await fakeApi([{ id: "req-5", file_url: "/artifacts/3/files/primary" }], {
    port,
  })
  await until(() => restarted.answers().length === 1)
  stop()
  await restarted.close()

  assert.equal(restarted.answers()[0].path, `${ROUTES}/req-5/pdf`)
})

test("a PDF the API refuses as too large is reported as the request's failure", async () => {
  const api = await fakeApi([{ id: "req-6", file_url: "/artifacts/3/files/primary" }], {
    pdfStatus: 413,
  })
  const stop = serveDocxSnapshots({
    apiUrl: api.url,
    key: KEY,
    print: async () => new TextEncoder().encode("%PDF-1.7 eighty pages of charts"),
    pollMs: 5,
  })

  await until(() => api.answers().length === 2)
  stop()
  await api.close()

  const [, answer] = api.answers()
  assert.equal(answer.path, `${ROUTES}/req-6/failure`)
  assert.deepEqual(JSON.parse(answer.body.toString()), {
    reason: "the printed document is too large to preview",
  })
})

test("a request waiting behind a slow print is printed at once, not after it", async () => {
  const api = await fakeApi([
    { id: "slow", file_url: "/artifacts/1/files/primary" },
    { id: "quick", file_url: "/artifacts/2/files/primary" },
  ])
  let finishSlow = () => {}
  const stop = serveDocxSnapshots({
    apiUrl: api.url,
    key: KEY,
    print: ({ fileUrl }) =>
      fileUrl.endsWith("/artifacts/1/files/primary")
        ? new Promise((resolve) => {
            finishSlow = () => resolve(new TextEncoder().encode("%PDF-1.7 slow"))
          })
        : Promise.resolve(new TextEncoder().encode("%PDF-1.7 quick")),
    // Longer than the test waits: the second request is taken without a pause.
    pollMs: 60_000,
  })

  await until(() => api.answers().length === 1)
  assert.equal(api.answers()[0].path, `${ROUTES}/quick/pdf`)
  finishSlow()
  await until(() => api.answers().length === 2)
  stop()
  await api.close()

  assert.equal(api.answers()[1].path, `${ROUTES}/slow/pdf`)
})

test("no more than three Word files are printed at once", async () => {
  const api = await fakeApi(
    ["a", "b", "c", "d"].map((id) => ({ id, file_url: `/artifacts/${id}/files/primary` })),
  )
  const finish: (() => void)[] = []
  const stop = serveDocxSnapshots({
    apiUrl: api.url,
    key: KEY,
    print: () =>
      new Promise((resolve) => {
        finish.push(() => resolve(new TextEncoder().encode("%PDF-1.7")))
      }),
    pollMs: 5,
  })

  await until(() => finish.length === 3)
  await new Promise((resolve) => setTimeout(resolve, 50))
  assert.equal(finish.length, 3)
  finish[0]()
  await until(() => finish.length === 4)
  finish.slice(1).forEach((done) => done())
  await until(() => api.answers().length === 4)
  stop()
  await api.close()
})

test("a poll the API never answers is given up, and polling goes on", async () => {
  const api = await fakeApi([{ id: "req-7", file_url: "/artifacts/3/files/primary" }], {
    unansweredPolls: 1,
  })
  const stop = serveDocxSnapshots({
    apiUrl: api.url,
    key: KEY,
    print: async () => new TextEncoder().encode("%PDF-1.7"),
    pollMs: 5,
    requestMs: 50,
  })

  await until(() => api.answers().length === 1)
  stop()
  await api.close()

  assert.equal(api.answers()[0].path, `${ROUTES}/req-7/pdf`)
})

test("a poll with another key is refused, and nothing is printed", async () => {
  const api = await fakeApi([{ id: "req-8", file_url: "/artifacts/3/files/primary" }])
  let printed = 0
  const stop = serveDocxSnapshots({
    apiUrl: api.url,
    key: "a-key-from-an-earlier-launch",
    print: async () => {
      printed += 1
      return new TextEncoder().encode("%PDF-1.7")
    },
    pollMs: 5,
  })

  await new Promise((resolve) => setTimeout(resolve, 50))
  stop()
  await api.close()

  assert.equal(printed, 0)
  assert.deepEqual(api.received, [])
})
