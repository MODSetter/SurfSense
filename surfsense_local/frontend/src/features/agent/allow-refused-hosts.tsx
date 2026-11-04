import { useState } from "react"

import { Button } from "@/components/ui/button"
import { allowAll } from "@/features/egress/api"
import { askEgress } from "@/features/egress/ask-egress"
import { intl } from "@/i18n/intl"

import type { AgentStep } from "./api"

/**
 * Under a web step refused a host the user has not allowed: the consent
 * question, asked on this click, since a turn cannot ask on its own.
 */
export function AllowRefusedHosts({
  refused,
}: {
  refused: NonNullable<AgentStep["refused"]>
}) {
  const [allowed, setAllowed] = useState(false)
  const [first, ...also] = refused.hosts
  if (!first) return null
  if (allowed) {
    return (
      <p className="mt-1 ml-5.5 text-xs text-muted-foreground">
        {intl.formatMessage({
          id: "agent_steps_hosts_allowed_status",
          defaultMessage: "Allowed. Ask the agent to try again.",
        })}
      </p>
    )
  }
  const destination = `host:${first}`
  const ask = async () => {
    const yes = await askEgress({
      destination,
      host: first,
      purpose: refused.purpose,
      also,
      allow: () => allowAll(destination, also),
    })
    if (yes) setAllowed(true)
  }
  return (
    <div className="mt-1 ml-5.5">
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => void ask()}
      >
        {intl.formatMessage(
          {
            id: "agent_steps_allow_hosts_button",
            defaultMessage: "Allow {hosts}",
          },
          { hosts: intl.formatList(refused.hosts, { type: "conjunction" }) }
        )}
      </Button>
    </div>
  )
}
