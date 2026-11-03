import { queryOptions } from "@tanstack/react-query"

import {
  listPlugins,
  pluginsQueryKey,
  thirdPartyAllowed,
  thirdPartyQueryKey,
} from "../api"

// What the `@` list reads, shared with startup, which loads it early so the
// list is ready when the composer arrives.

export const pluginListQuery = queryOptions({
  queryKey: pluginsQueryKey,
  queryFn: ({ signal }) => listPlugins(signal),
})

export const thirdPartyQuery = queryOptions({
  queryKey: thirdPartyQueryKey,
  queryFn: ({ signal }) => thirdPartyAllowed(signal),
})
