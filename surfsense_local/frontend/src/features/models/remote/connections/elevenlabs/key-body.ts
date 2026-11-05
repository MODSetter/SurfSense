import { intl } from "@/i18n/intl"

/** What a key has to allow, said where it is asked for. */
export const elevenLabsKeyBody = () =>
  intl.formatMessage({
    id: "models_elevenlabs_key_body",
    defaultMessage:
      "The key needs access to Text to Speech, Models and Voices. User access is optional, and lets SurfSense hide voices your plan can’t use.",
  })
