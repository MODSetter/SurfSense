import { useState } from "react"

import { errorToast } from "@/features/feedback/error-toast"
import { intl } from "@/i18n/intl"

import { refusalText } from "./refusal-text"
import type { MoveReady, PlanResult, StorageKind } from "./storage-types"

/** From choosing a folder to the confirmation; main holds the plan itself. */
export function useMoveFlow() {
  const [ready, setReady] = useState<MoveReady | null>(null)
  const [planning, setPlanning] = useState<StorageKind | null>(null)

  const settle = async (kind: StorageKind, asked: Promise<PlanResult>) => {
    setPlanning(kind)
    try {
      const result = await asked
      if (result.status === "ready") setReady(result)
      if (result.status === "refused") {
        errorToast(
          intl.formatMessage({
            id: "storage_refusal_title",
            defaultMessage: "Can’t use this folder",
          }),
          { description: refusalText(result) }
        )
      }
    } finally {
      setPlanning(null)
    }
  }

  const bridge = window.surfsense?.storage
  return {
    ready,
    planning,
    choose: (kind: StorageKind) => {
      if (bridge) void settle(kind, bridge.choose(kind))
    },
    useDefault: (kind: StorageKind) => {
      if (bridge) void settle(kind, bridge.planDefault(kind))
    },
    confirm: () => {
      setReady(null)
      void bridge?.start()
    },
    dismiss: () => setReady(null),
  }
}
