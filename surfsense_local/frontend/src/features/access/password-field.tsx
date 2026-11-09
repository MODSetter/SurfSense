import { useState, type ComponentProps } from "react"

import { ViewIcon, ViewOffIcon } from "@/components/ui/icons"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { intl } from "@/i18n/intl"

/**
 * A password typed once, with an eye that shows it: checking it by eye
 * replaces typing it twice, which repeats a pasted typo anyway.
 */
export function PasswordField(
  props: Omit<ComponentProps<typeof InputGroupInput>, "type">
) {
  const [shown, setShown] = useState(false)
  return (
    <InputGroup>
      <InputGroupInput {...props} type={shown ? "text" : "password"} />
      <InputGroupAddon align="inline-end">
        <InputGroupButton
          size="icon-xs"
          aria-label={
            shown
              ? intl.formatMessage({
                  id: "access_reveal_hide_aria",
                  defaultMessage: "Hide password",
                })
              : intl.formatMessage({
                  id: "access_reveal_show_aria",
                  defaultMessage: "Show password",
                })
          }
          aria-pressed={shown}
          onClick={() => setShown((value) => !value)}
          disabled={props.disabled}
        >
          {shown ? <ViewOffIcon /> : <ViewIcon />}
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  )
}
