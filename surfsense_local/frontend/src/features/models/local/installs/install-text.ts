import { intl } from "@/i18n/intl"

import type { InstallEvent } from "../chat/api"
import { notRunnableLine } from "../chat/not-runnable-text"

// The codes are `InstallCode` in the backend's
// modules/llm/catalog/local/install/codes.py; keep the two in sync. English
// mirrors the sentence the backend sends with each, which stays the fallback
// for a code that has no line here.
const installText: Record<string, (event: InstallEvent) => string | null> = {
  queued: () =>
    intl.formatMessage({
      id: "models_install_step_queued_status",
      defaultMessage: "Waiting for the download ahead of it",
    }),
  checking: () =>
    intl.formatMessage({
      id: "models_install_step_checking_status",
      defaultMessage: "Checking the model",
    }),
  preparing_download: () =>
    intl.formatMessage({
      id: "models_install_step_preparing_download_status",
      defaultMessage: "Preparing download",
    }),
  downloading: () =>
    intl.formatMessage({
      id: "models_install_step_downloading_status",
      defaultMessage: "Downloading",
    }),
  checking_retrieval: () =>
    intl.formatMessage({
      id: "models_install_step_checking_retrieval_status",
      defaultMessage: "Checking that it finds answers",
    }),
  preparing_runtime: () =>
    intl.formatMessage({
      id: "models_install_step_preparing_runtime_status",
      defaultMessage: "Preparing the model runtime",
    }),
  loading_model: () =>
    intl.formatMessage({
      id: "models_install_step_loading_model_status",
      defaultMessage: "Loading the model",
    }),
  loading_image_support: () =>
    intl.formatMessage({
      id: "models_install_step_loading_image_support_status",
      defaultMessage: "Loading image support",
    }),
  loading_draft_model: () =>
    intl.formatMessage({
      id: "models_install_step_loading_draft_model_status",
      defaultMessage: "Loading the draft model",
    }),
  selecting: () =>
    intl.formatMessage({
      id: "models_install_step_selecting_status",
      defaultMessage: "Selecting model",
    }),
  ready: () =>
    intl.formatMessage({
      id: "models_install_step_ready_status",
      defaultMessage: "Model is ready",
    }),
  ready_after_restart: () =>
    intl.formatMessage({
      id: "models_install_step_ready_after_restart_status",
      defaultMessage:
        "Downloaded. It becomes available once the runtime restarts.",
    }),
  cancelled: () =>
    intl.formatMessage({
      id: "models_install_step_cancelled_status",
      defaultMessage: "Installation cancelled",
    }),
  failed: () =>
    intl.formatMessage({
      id: "models_error_install_failed",
      defaultMessage: "The model could not be installed. Retry the download.",
    }),
  file_gone: () =>
    intl.formatMessage({
      id: "models_error_install_file_gone",
      defaultMessage:
        "This model is no longer available where SurfSense expects it.",
    }),
  checksum_mismatch: () =>
    intl.formatMessage({
      id: "models_error_install_checksum_mismatch",
      defaultMessage:
        "The downloaded file did not match the expected one. Retry the download.",
    }),
  not_enough_disk: (event) =>
    event.type === "error" &&
    typeof event.needed_bytes === "number" &&
    typeof event.free_bytes === "number"
      ? intl.formatMessage(
          {
            id: "models_error_install_not_enough_disk",
            defaultMessage:
              "This download needs {needed, number, ::unit/gigabyte .#} free; this computer has {free, number, ::unit/gigabyte .#}.",
          },
          {
            needed: event.needed_bytes / 1e9,
            free: event.free_bytes / 1e9,
          }
        )
      : null,
  too_big: () =>
    intl.formatMessage({
      id: "models_error_install_too_big",
      defaultMessage:
        "This build is too big for this computer. Pick a smaller one.",
    }),
  not_a_model: () =>
    intl.formatMessage({
      id: "models_error_install_not_a_model",
      defaultMessage: "This file is not a model SurfSense can run.",
    }),
  no_engine: () =>
    intl.formatMessage({
      id: "models_error_install_no_engine",
      defaultMessage: "This build of SurfSense cannot run this model.",
    }),
}

/**
 * What an install event says: the interface's own line for its code, or the
 * backend's sentence for a code it does not know. Empty when it has neither.
 * A refusal for what the file is carries the catalog's code for it, worded as
 * the catalog's rows word it.
 */
export function installMessage(event: InstallEvent): string {
  const code = event.code
  const own =
    code != null && Object.hasOwn(installText, code)
      ? installText[code](event)
      : notRunnableLine(code)
  return own ?? event.message ?? ""
}
