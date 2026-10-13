import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { gitAboveDataFolder, gitRootAbove, holds } from "./git-repository.ts"

/** A tree with a `.git` folder at its root, like a repository checked out. */
function repository(): string {
  const root = mkdtempSync(join(tmpdir(), "gitrepo-"))
  mkdirSync(join(root, ".git"))
  return root
}

/** A tree with no `.git` anywhere above it. */
function plain(): string {
  return mkdtempSync(join(tmpdir(), "plain-"))
}

// The machine's own folders can hold a repository (a home folder kept in git,
// the very case the issue reports), so every walk here stops at the test
// tree's root and never sees them. `plain()` is the root, and the walk from
// anything under it never reaches it.

test("finds a .git folder directly on the folder", () => {
  const root = repository()
  assert.equal(gitRootAbove(root), root)
})

test("finds a .git folder above the folder", () => {
  const root = repository()
  const inner = join(root, "deep", "deeper")
  mkdirSync(inner, { recursive: true })
  assert.equal(gitRootAbove(inner), root)
})

test("finds a .git file, as a worktree or submodule names its repository", () => {
  const root = mkdtempSync(join(tmpdir(), "gitfile-"))
  writeFileSync(join(root, ".git"), "gitdir: elsewhere")
  assert.equal(gitRootAbove(join(root, "sub")), root)
})

test("finds nothing when no .git stands above", () => {
  const root = plain()
  const sub = join(root, "sub")
  mkdirSync(sub)
  assert.equal(gitRootAbove(sub, root), null)
})

test("holds says the folder inside the repository is held", () => {
  const root = repository()
  assert.ok(holds(root, join(root, "data", "agent")))
})

test("holds refuses a folder outside the repository", () => {
  const ours = repository()
  const theirs = plain()
  assert.equal(holds(ours, join(theirs, "agent")), false)
})

test("a repository above the data folder is reported", () => {
  const root = repository()
  const dataDir = join(root, ".surfsense")
  mkdirSync(dataDir)
  assert.equal(gitAboveDataFolder(dataDir), root)
})

test("no repository above the data folder is safe", () => {
  const root = plain()
  const dataDir = join(root, ".surfsense")
  mkdirSync(dataDir)
  assert.equal(gitAboveDataFolder(dataDir, root), null)
})

test("a repository beside the data folder does not hold it", () => {
  // The repository holds a checkout; the data folder is not inside it. Both
  // sit under `root`, so no `.git` above `root` can reach in and confuse the
  // two cases, whatever repositories the machine's own folders hold.
  const root = plain()
  const repo = join(root, "checkout")
  mkdirSync(join(repo, ".git"), { recursive: true })
  const dataDir = join(root, ".surfsense")
  mkdirSync(dataDir)
  assert.equal(holds(repo, dataDir), false)
})
