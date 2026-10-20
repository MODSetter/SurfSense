import type { OwnApp } from "../../api"

/** The own-app fields as typed: scopes space-separated, a blank secret left out. */
export type OwnAppDraft = {
  clientId: string
  clientSecret: string
  scopes: string
}

export const EMPTY_OWN_APP: OwnAppDraft = {
  clientId: "",
  clientSecret: "",
  scopes: "",
}

export function asOwnApp(draft: OwnAppDraft): OwnApp {
  const scopes = draft.scopes.split(/\s+/).filter(Boolean)
  return {
    client_id: draft.clientId.trim(),
    ...(draft.clientSecret ? { client_secret: draft.clientSecret } : {}),
    ...(scopes.length ? { scopes } : {}),
  }
}
