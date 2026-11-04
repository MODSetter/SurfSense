import { useState, type ComponentProps } from "react"

import { Select } from "@/components/ui/select"
import {
  readMotionPreference,
  setMotionPreference,
  type MotionPreference,
} from "@/features/motion-preference/motion-preference"
import { intl } from "@/i18n/intl"

export function ReduceMotionSelect(
  props: Omit<ComponentProps<typeof Select>, "value" | "onChange">
) {
  const [preference, setPreference] = useState(readMotionPreference)

  return (
    <Select
      {...props}
      value={preference}
      onChange={(event) => {
        const next = event.target.value as MotionPreference
        setPreference(next)
        setMotionPreference(next)
      }}
    >
      <option value="system">
        {intl.formatMessage({
          id: "settings_general_reduce_motion_system_label",
          defaultMessage: "Match system",
        })}
      </option>
      <option value="on">
        {intl.formatMessage({
          id: "settings_general_reduce_motion_on_label",
          defaultMessage: "On",
        })}
      </option>
      <option value="off">
        {intl.formatMessage({
          id: "settings_general_reduce_motion_off_label",
          defaultMessage: "Off",
        })}
      </option>
    </Select>
  )
}
