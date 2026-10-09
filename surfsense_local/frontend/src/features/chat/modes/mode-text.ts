import type {
  CapabilityReason,
  ChatMode,
} from "@/features/models/capability/api"
import { intl } from "@/i18n/intl"

export function modeLabel(mode: ChatMode) {
  return mode === "agentic"
    ? intl.formatMessage({
        id: "chat_mode_agentic_label",
        defaultMessage: "Agentic",
      })
    : intl.formatMessage({
        id: "chat_mode_basic_label",
        defaultMessage: "Basic (Q&A)",
      })
}

export function modeDescription(mode: ChatMode) {
  return mode === "agentic"
    ? intl.formatMessage({
        id: "chat_mode_agentic_body",
        defaultMessage:
          "Works on your files in steps, and makes and edits documents.",
      })
    : intl.formatMessage({
        id: "chat_mode_basic_body",
        defaultMessage: "Answers from your sources, with Studio for documents.",
      })
}

/** One line per mode, short enough for the new chat's menu. */
export function modeShortDescription(mode: ChatMode) {
  return mode === "agentic"
    ? intl.formatMessage({
        id: "chat_mode_agentic_short_body",
        defaultMessage: "Does tasks across your files",
      })
    : intl.formatMessage({
        id: "chat_mode_basic_short_body",
        defaultMessage: "Answers from your sources",
      })
}

/** The tag beside Agentic; a model that passed gets none. */
export function agenticReasonTag(reason: CapabilityReason) {
  if (reason.code === "measured_pass") return null
  return intl.formatMessage(
    {
      id: "chat_mode_agentic_reason_label",
      defaultMessage:
        "{code, select, measured_near {May need nudges} measured_below {Low score} assumed {Expected to pass} local_copy {Local copy} other {Not tested}}",
    },
    { code: reason.code }
  )
}

/** What Agentic says for this model: its score, a note, or the untested warning. */
export function agenticReasonText(reason: CapabilityReason) {
  return intl.formatMessage(
    {
      id: "chat_mode_agentic_reason_body",
      defaultMessage:
        "{code, select, measured_pass {Passed {passed, number} of {counted, number} Agentic tests.} measured_near {Passed {passed, number} of {counted, number} Agentic tests. It may need a nudge, such as asking it to check each page.} measured_below {Passed {passed, number} of {counted, number} Agentic tests, so it may stop early or make mistakes.} assumed {Not tested yet: SurfSense expects this flagship model to do well.} local_copy {Passed on its full-size version. A local copy may do worse.} other {Not tested with this model yet, so it may stop early or make mistakes.}}",
    },
    {
      code: reason.code,
      passed: Number(reason.values.passed ?? 0),
      counted: Number(reason.values.counted ?? 0),
    }
  )
}

/** Why Agentic cannot be picked: a technical gate, never a score. */
export function agenticBlockedText(blocked: string) {
  return intl.formatMessage(
    {
      id: "chat_mode_agentic_blocked_body",
      defaultMessage:
        "{blocked, select, agent_not_installed {This install doesn’t include the agent.} window_below_floor {This model’s context window is too small for Agentic mode.} other {This model can’t use tools.}}",
    },
    { blocked }
  )
}

/** Why the API would not open an Agentic chat, by the code it answered. */
export function agenticRefusedText(code: string) {
  return intl.formatMessage(
    {
      id: "chat_mode_agentic_refused_toast",
      defaultMessage:
        "{code, select, agent_unavailable {The agent didn’t start. Try again, or start a Basic (Q&A) chat.} agent_not_installed {This install doesn’t include the agent. Start a Basic (Q&A) chat.} window_below_floor {This model’s context window is too small for Agentic mode.} tool_calls_unsupported {This model can’t use tools, so it can’t run Agentic mode.} other {Couldn’t start an Agentic chat.}}",
    },
    { code }
  )
}

/** The codes the API refuses an Agentic chat with, which `agenticRefusedText` words. */
export const AGENTIC_REFUSALS = new Set([
  "agent_unavailable",
  "agent_not_installed",
  "window_below_floor",
  "tool_calls_unsupported",
])
