import type { SignInHeader } from "../api"
import { filledHeaders } from "../headers/filled-headers"
import {
  EMPTY_OWN_APP,
  type OwnAppDraft,
} from "../sign-in/own-app/own-app-draft"

/** How a key goes: most servers read `Authorization: Bearer`, some Basic, some their own header. */
export type SendAs = "bearer" | "basic" | "custom"

/** What the connection fields hold as typed; values are never filled from the API. */
export type ConnectionDraft = {
  key: string
  sendAs: SendAs
  // The header a `custom` key goes in, such as `x-api-key`.
  headerName: string
  // Further headers, for a server reading more than one.
  extra: SignInHeader[]
  ownApp: OwnAppDraft
}

export const EMPTY_CONNECTION: ConnectionDraft = {
  key: "",
  sendAs: "bearer",
  headerName: "",
  extra: [],
  ownApp: EMPTY_OWN_APP,
}

/** A stored plugin's header names, so editing asks only for the values again. */
export function draftFromNames(names: string[]): ConnectionDraft {
  const [first, ...rest] = names
  const extra = rest.map((name) => ({ name, value: "" }))
  if (!first || first.toLowerCase() === "authorization") {
    return { ...EMPTY_CONNECTION, extra }
  }
  return { ...EMPTY_CONNECTION, sendAs: "custom", headerName: first, extra }
}

/** The headers to send; none when no key or header was given. */
export function connectionHeaders(draft: ConnectionDraft): SignInHeader[] {
  const extra = filledHeaders(draft.extra)
  if (!draft.key) return extra
  return [{ name: keyHeader(draft), value: keyValue(draft) }, ...extra]
}

/** A key is ready to send once a custom one names its header. */
export function keyComplete(draft: ConnectionDraft): boolean {
  return draft.sendAs !== "custom" || draft.headerName.trim() !== ""
}

function keyHeader(draft: ConnectionDraft): string {
  return draft.sendAs === "custom" ? draft.headerName.trim() : "Authorization"
}

function keyValue(draft: ConnectionDraft): string {
  if (draft.sendAs === "bearer") return `Bearer ${draft.key}`
  if (draft.sendAs === "basic") {
    // `user:password` is encoded as Basic asks; an already-encoded value is sent as is.
    return `Basic ${draft.key.includes(":") ? btoa(draft.key) : draft.key}`
  }
  return draft.key
}
