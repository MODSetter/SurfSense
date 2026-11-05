import { intl } from "@/i18n/intl"

import type { MoveFailureReason, PlanResult, StorageRefusalCode } from "./storage-types"

const REFUSALS: Record<StorageRefusalCode, () => string> = {
  same_folder: () =>
    intl.formatMessage({
      id: "storage_refusal_same_folder_error",
      defaultMessage: "SurfSense already uses this folder.",
    }),
  inside_current: () =>
    intl.formatMessage({
      id: "storage_refusal_inside_current_error",
      defaultMessage: "Choose a folder outside the one SurfSense uses now.",
    }),
  inside_app: () =>
    intl.formatMessage({
      id: "storage_refusal_inside_app_error",
      defaultMessage:
        "Choose a folder outside the app. An update would delete anything inside it.",
    }),
  network_drive: () =>
    intl.formatMessage({
      id: "storage_refusal_network_drive_error",
      defaultMessage:
        "Your data can’t be kept on a network drive. Choose a drive on this computer.",
    }),
  not_writable: () =>
    intl.formatMessage({
      id: "storage_refusal_not_writable_error",
      defaultMessage: "SurfSense can’t write to this folder.",
    }),
  no_large_files: () =>
    intl.formatMessage({
      id: "storage_refusal_no_large_files_error",
      defaultMessage:
        "This drive can’t hold files over 4 GB, and many models are larger. Choose another, or reformat it as exFAT or NTFS.",
    }),
  no_hard_links: () =>
    intl.formatMessage({
      id: "storage_refusal_no_hard_links_error",
      defaultMessage:
        "This drive’s format can’t hold your data, though it can hold models. Choose a drive formatted as NTFS, APFS or ext4.",
    }),
  target_occupied: () =>
    intl.formatMessage({
      id: "storage_refusal_target_occupied_error",
      defaultMessage:
        "This folder already has files in it that aren’t SurfSense’s. Choose another.",
    }),
  not_enough_room: () =>
    intl.formatMessage({
      id: "storage_refusal_not_enough_room_error",
      defaultMessage: "This drive doesn’t have enough free space.",
    }),
}

export function refusalText(
  refusal: Extract<PlanResult, { status: "refused" }>
): string {
  const { code, neededBytes, freeBytes } = refusal
  if (code === "not_enough_room" && neededBytes !== undefined && freeBytes !== undefined) {
    return intl.formatMessage(
      {
        id: "storage_refusal_not_enough_room_amounts_error",
        defaultMessage:
          "This move needs {needed, number, ::unit/gigabyte .#} free; this drive has {free, number, ::unit/gigabyte .#}.",
      },
      { needed: neededBytes / 1e9, free: freeBytes / 1e9 }
    )
  }
  return REFUSALS[code]()
}

export function moveFailureText(reason: MoveFailureReason): string {
  if (reason === "no_room") {
    return intl.formatMessage({
      id: "storage_move_failed_no_room_error",
      defaultMessage: "The drive ran out of space.",
    })
  }
  if (reason === "verify_failed") {
    return intl.formatMessage({
      id: "storage_move_failed_verify_error",
      defaultMessage:
        "The copy didn’t match the original, so this drive may be failing.",
    })
  }
  return intl.formatMessage({
    id: "storage_move_failed_error",
    defaultMessage: "Something went wrong while copying your files.",
  })
}
