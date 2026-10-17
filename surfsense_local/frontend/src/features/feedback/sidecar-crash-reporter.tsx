import { useEffect } from "react"

import { intl } from "@/i18n/intl"
import type { SidecarCrash } from "@/lib/api"

import { errorToast } from "./error-toast"

function affectedPart(name: string): string {
  switch (name) {
    case "api":
      return "core"
    case "worker-ingest":
      return "documents"
    case "worker-studio":
      return "studio"
    case "llamacpp":
      return "chat"
    case "sdcpp":
      return "images"
    case "audiocpp":
      return "audio"
    case "opencode":
      return "agent"
    default:
      return "other"
  }
}

function reportCrash(crash: SidecarCrash): void {
  const part = affectedPart(crash.name)
  errorToast(
    intl.formatMessage(
      {
        id: "feedback_sidecar_crashed_toast",
        defaultMessage:
          "{part, select, core {SurfSense stopped working} documents {Document processing stopped} studio {Studio processing stopped} chat {Local chat stopped} images {Image generation stopped} audio {Audio generation stopped} agent {The agent stopped} other {A background service stopped}}",
      },
      { part }
    ),
    {
      // Electron reports the agent only once it stops restarting it, and the
      // next Agentic message earns it another start.
      description:
        part === "agent"
          ? intl.formatMessage({
              id: "feedback_agent_crashed_body",
              defaultMessage:
                "SurfSense will try again with your next Agentic message.",
            })
          : intl.formatMessage({
              id: "feedback_sidecar_crashed_body",
              defaultMessage: "Restart SurfSense to restore it.",
            }),
      reportError: `Sidecar ${crash.name} crashed (code=${crash.code})`,
    }
  )
}

/** One app-wide listener for unexpected exits from supervised processes. */
export function SidecarCrashReporter() {
  useEffect(() => window.surfsense?.sidecars?.onCrash(reportCrash), [])
  return null
}
