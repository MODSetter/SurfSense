import type { QueryClient } from "@tanstack/react-query"

import { followInstalls, type InstallJob } from "./api"
import { announce } from "./announce"
import { INSTALLS_QUERY_KEY } from "./installs-query-key"
import { isRunning } from "./job-state"

const FIRST_RETRY_MS = 1_000
const LAST_RETRY_MS = 10_000

type Feed = {
  holders: number
  stop: () => void
}

type Watched = {
  /** Jobs this window saw running or started, so only their end is announced. */
  seen: Set<string>
  announced: Set<string>
}

const feeds = new WeakMap<QueryClient, Feed>()
const watched = new WeakMap<QueryClient, Watched>()

function watchedBy(client: QueryClient): Watched {
  let state = watched.get(client)
  if (!state) {
    state = { seen: new Set(), announced: new Set() }
    watched.set(client, state)
  }
  return state
}

function settle(client: QueryClient) {
  const state = watchedBy(client)
  for (const job of client.getQueryData<InstallJob[]>(INSTALLS_QUERY_KEY) ??
    []) {
    if (isRunning(job)) {
      state.seen.add(job.id)
    } else if (state.seen.has(job.id) && !state.announced.has(job.id)) {
      state.announced.add(job.id)
      announce(client, job)
    }
  }
}

/** The API's whole list replaces the cache: it is the only account there is. */
export function receiveJobs(client: QueryClient, jobs: InstallJob[]) {
  client.setQueryData(INSTALLS_QUERY_KEY, jobs)
  settle(client)
}

/** A job this window started. The feed may already hold a newer frame of it. */
export function noteStarted(client: QueryClient, job: InstallJob) {
  watchedBy(client).seen.add(job.id)
  client.setQueryData<InstallJob[]>(INSTALLS_QUERY_KEY, (jobs = []) =>
    jobs.some((known) => known.id === job.id) ? jobs : [...jobs, job]
  )
  settle(client)
}

function wait(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve) => {
    const timeout = setTimeout(resolve, ms)
    signal.addEventListener("abort", () => {
      clearTimeout(timeout)
      resolve()
    })
  })
}

async function follow(client: QueryClient, signal: AbortSignal) {
  let retry = FIRST_RETRY_MS
  while (!signal.aborted) {
    try {
      for await (const frame of followInstalls(signal)) {
        retry = FIRST_RETRY_MS
        receiveJobs(client, frame.jobs)
      }
    } catch {
      // The API restarting or not up yet; the next connection's first frame
      // is the whole list, so nothing missed needs replaying.
    }
    await wait(retry, signal)
    retry = Math.min(retry * 2, LAST_RETRY_MS)
  }
}

/** One stream per client however many views read it; returns the release. */
export function retainInstallFeed(client: QueryClient): () => void {
  let feed = feeds.get(client)
  if (!feed) {
    // Kept while nothing reads it: a job's end is announced with Settings closed.
    client.setQueryDefaults(INSTALLS_QUERY_KEY, {
      gcTime: Number.POSITIVE_INFINITY,
      staleTime: Number.POSITIVE_INFINITY,
    })
    const controller = new AbortController()
    feed = { holders: 0, stop: () => controller.abort() }
    feeds.set(client, feed)
    void follow(client, controller.signal)
  }
  feed.holders += 1
  const held = feed
  return () => {
    held.holders -= 1
    if (held.holders === 0) {
      held.stop()
      feeds.delete(client)
    }
  }
}
