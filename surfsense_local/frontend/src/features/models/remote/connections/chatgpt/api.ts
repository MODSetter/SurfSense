import { askEgress } from "@/features/egress/ask-egress"
import { allowAll } from "@/features/egress/api"
import { requestJson, requestVoid } from "@/lib/api"

import type { ModelType } from "../../../model-type"

/** The provider-picker value for a ChatGPT subscription; no manifest entry has it. */
export const CHATGPT_PROVIDER = "chatgpt"

export type SignInStarted = { flow_id: string; authorize_url: string }

export type SignIn = {
  status: "waiting" | "signed_in" | "failed"
  connection_id: number | null
  message: string | null
}

/** A new connection's label, or the connection whose sign-in this renews. */
export type SignInTarget = { label: string } | { connection_id: number }

type RefusedHost = { destination: string; host: string }

/** What a ChatGPT connection would fill, and the hosts its sign-in still needs. */
export type SignInOption = { serves: ModelType[]; hosts: RefusedHost[] }

export const signInOptionQueryKey = ["chatgpt-sign-in-option"] as const

export function getSignInOption(signal?: AbortSignal): Promise<SignInOption> {
  return requestJson<SignInOption>("/llm/connections/chatgpt", { signal })
}

/** Nothing was started: the user kept a host the sign-in needs switched off. */
export class HostDeclinedError extends Error {
  readonly host: string

  constructor(host: string) {
    super(host)
    this.name = "HostDeclinedError"
    this.host = host
  }
}

/**
 * Starts a sign-in once both hosts it reaches, OpenAI's sign-in and its API,
 * are allowed: asked up front, in one question for every host still off.
 */
export async function startSignIn(
  target: SignInTarget
): Promise<SignInStarted> {
  const { hosts } = await getSignInOption()
  const [first, ...rest] = hosts
  if (first) {
    const also = rest.map(({ host }) => host)
    const allowed = await askEgress({
      destination: first.destination,
      host: first.host,
      also,
      allow: () => allowAll(first.destination, also),
    })
    if (!allowed) throw new HostDeclinedError(first.host)
  }
  return requestJson<SignInStarted>("/llm/connections/chatgpt/sign-in", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(target),
  })
}

export function getSignIn(
  flowId: string,
  signal?: AbortSignal
): Promise<SignIn> {
  return requestJson<SignIn>(`/llm/connections/chatgpt/sign-in/${flowId}`, {
    signal,
  })
}

export function cancelSignIn(flowId: string): Promise<void> {
  return requestVoid(`/llm/connections/chatgpt/sign-in/${flowId}`, {
    method: "DELETE",
  })
}

export function signOut(connectionId: number): Promise<void> {
  return requestVoid(`/llm/connections/${connectionId}/sign-in`, {
    method: "DELETE",
  })
}
