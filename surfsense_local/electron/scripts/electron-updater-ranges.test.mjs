import assert from "node:assert/strict"
import { createHash } from "node:crypto"
import { mkdtempSync, readFileSync, statSync, writeFileSync } from "node:fs"
import { createServer, request } from "node:http"
import { createRequire } from "node:module"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { Readable } from "node:stream"
import test from "node:test"

// electron-updater asks GitHub for one range per request. A proxy that drops
// the Range header answers each with the whole file, which electron-updater
// 6.8.9 writes out once per range until the disk fills;
// patches/electron-updater@6.8.9.patch makes any reply but 206 end the
// differential attempt, so the update falls back to one full download.
const require = createRequire(import.meta.url)
const updaterRequire = createRequire(require.resolve("electron-updater"))
const { CancellationToken, HttpExecutor } = updaterRequire("builder-util-runtime")
const { GenericDifferentialDownloader } = updaterRequire(
  "./differentialDownloader/GenericDifferentialDownloader"
)

/** builder-util-runtime's executor over node:http, as Electron's net is under the app. */
class NodeExecutor extends HttpExecutor {
  createRequest(options, callback) {
    return request(options, callback)
  }
}

const BLOCK = 100_000
const BLOCKS = 20
const CHANGED = [1, 5, 9, 13, 17]

const oldFile = Buffer.alloc(BLOCK * BLOCKS, 1)
const newFile = Buffer.from(oldFile)
for (const i of CHANGED) newFile.fill(2, i * BLOCK, (i + 1) * BLOCK)

function blockMap(file) {
  const checksums = Array.from({ length: BLOCKS }, (_, i) =>
    createHash("sha256").update(file.subarray(i * BLOCK, (i + 1) * BLOCK)).digest("base64")
  )
  return {
    version: "2",
    files: [{ name: "file", offset: 0, checksums, sizes: Array(BLOCKS).fill(BLOCK) }],
  }
}

/** Streams `size` bytes lazily, so the bytes sent show how much the client read. */
function body(size, source, seen) {
  let offset = 0
  return new Readable({
    read() {
      if (offset >= size) return this.push(null)
      const n = Math.min(64 * 1024, size - offset)
      const chunk = source ? source.subarray(offset, offset + n) : Buffer.alloc(n, 3)
      offset += n
      seen.bytes += n
      this.push(chunk)
    },
  })
}

/** A server for `file` that honours Range, or ignores it and sends the whole file. */
async function serve({ honoursRange, size = newFile.length, source = newFile }) {
  const seen = { requests: 0, bytes: 0 }
  const server = createServer((req, res) => {
    seen.requests++
    const range = /^bytes=(\d+)-(\d+)$/.exec(req.headers.range ?? "")
    if (honoursRange && range) {
      const [start, end] = [Number(range[1]), Number(range[2])]
      res.writeHead(206, {
        "accept-ranges": "bytes",
        "content-range": `bytes ${start}-${end}/${size}`,
        "content-length": end - start + 1,
      })
      seen.bytes += end - start + 1
      res.end(source.subarray(start, end + 1))
      return
    }
    res.writeHead(200, { "accept-ranges": "bytes", "content-length": size })
    const stream = body(size, source, seen)
    res.on("close", () => stream.destroy())
    stream.pipe(res)
  })
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve))
  const url = new URL(`http://127.0.0.1:${server.address().port}/SurfSense-Setup.exe`)
  return { url, seen, close: () => new Promise((resolve) => server.close(resolve)) }
}

function downloader(url, dir) {
  writeFileSync(join(dir, "installer.exe"), oldFile)
  const silent = { info() {}, warn() {}, error() {} }
  const info = { sha512: createHash("sha512").update(newFile).digest("base64"), size: newFile.length }
  return new GenericDifferentialDownloader(info, new NodeExecutor(), {
    newUrl: url,
    oldFile: join(dir, "installer.exe"),
    newFile: join(dir, "update.exe"),
    logger: silent,
    isUseMultipleRangeRequest: false,
    requestHeaders: {},
    cancellationToken: new CancellationToken(),
  })
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 200))

test("a server that honours Range sends only the changed blocks", async (t) => {
  const server = await serve({ honoursRange: true })
  t.after(server.close)
  const dir = mkdtempSync(join(tmpdir(), "ranges-"))

  await downloader(server.url, dir).download(blockMap(oldFile), blockMap(newFile))

  assert.deepEqual(readFileSync(join(dir, "update.exe")), newFile)
  assert.equal(server.seen.requests, CHANGED.length)
  assert.equal(server.seen.bytes, CHANGED.length * BLOCK)
})

test("a reply that ignores Range ends the differential download at once", async (t) => {
  const server = await serve({ honoursRange: false })
  t.after(server.close)
  const dir = mkdtempSync(join(tmpdir(), "ranges-"))

  await assert.rejects(
    downloader(server.url, dir).download(blockMap(oldFile), blockMap(newFile)),
    /206/
  )
  await settle()

  assert.equal(server.seen.requests, 1)
  // Only the unchanged first block, copied from installer.exe, reached the file.
  assert.ok(statSync(join(dir, "update.exe")).size <= BLOCK)
})

test("the AppImage's blockmap read stops at a reply that ignores Range", async (t) => {
  const size = 256 * 1024 * 1024
  const server = await serve({ honoursRange: false, size, source: null })
  t.after(server.close)
  const dir = mkdtempSync(join(tmpdir(), "ranges-"))

  await assert.rejects(downloader(server.url, dir).readRemoteBytes(size - 1000, size - 1), /206/)
  await settle()

  assert.equal(server.seen.requests, 1)
  assert.ok(server.seen.bytes < size / 4, `read ${server.seen.bytes} of ${size} bytes`)
})
