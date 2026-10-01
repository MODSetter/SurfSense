import type { SearchSource } from "@/features/models/local/chat/search-source"
import { EMBEDDING_SEARCH } from "@/features/embedding/huggingface-search"
import { intl } from "@/i18n/intl"

import type { OnboardingStepKind } from "./kinds/step-kind"

/** What each step says, and which search and notice it shows. */
export const STEP_COPY: Record<
  OnboardingStepKind,
  {
    title: () => string
    description: () => string
    noLocal: () => string
    /** Hugging Face search, GGUF unless a source is given; null for none. */
    search: { source?: SearchSource; note?: () => string } | null
    /** Said below the list, where a choice has a consequence to state. */
    notice?: () => string
  }
> = {
  text_gen: {
    title: () =>
      intl.formatMessage({
        id: "onboarding_chat_step_title",
        defaultMessage: "Choose a text generation model",
      }),
    description: () =>
      intl.formatMessage({
        id: "onboarding_chat_step_body",
        defaultMessage:
          "Answers you in chat. Run one on this computer so your chats stay private, or use one from a server.",
      }),
    noLocal: () =>
      intl.formatMessage({
        id: "onboarding_chat_step_no_local_empty",
        defaultMessage:
          "No tested model can run on this computer. Use a server instead.",
      }),
    search: {},
  },
  image_gen: {
    title: () =>
      intl.formatMessage({
        id: "onboarding_image_step_title",
        defaultMessage: "Choose an image generation model",
      }),
    description: () =>
      intl.formatMessage({
        id: "onboarding_image_step_body",
        defaultMessage:
          "Creates images for you. Run one on this computer, or use one from a server.",
      }),
    noLocal: () =>
      intl.formatMessage({
        id: "onboarding_image_step_no_local_empty",
        defaultMessage:
          "Image models cannot run on this computer. Use a server instead.",
      }),
    // sd.cpp has no search: its models are the few the catalog ships.
    search: null,
  },
  image_edit: {
    title: () =>
      intl.formatMessage({
        id: "onboarding_image_edit_step_title",
        defaultMessage: "Choose an image editing model",
      }),
    description: () =>
      intl.formatMessage({
        id: "onboarding_image_edit_step_body",
        defaultMessage:
          "Edits images for you. Run one on this computer, or use one from a server.",
      }),
    noLocal: () =>
      intl.formatMessage({
        id: "onboarding_image_edit_step_no_local_empty",
        defaultMessage:
          "Image editing models cannot run on this computer. Use a server instead.",
      }),
    // Nor has it for editing: the same few models.
    search: null,
  },
  video_gen: {
    title: () =>
      intl.formatMessage({
        id: "onboarding_video_step_title",
        defaultMessage: "Choose a video generation model",
      }),
    description: () =>
      intl.formatMessage({
        id: "onboarding_video_step_body",
        defaultMessage:
          "Makes short video clips. Run one on this computer, or use one from a server.",
      }),
    noLocal: () =>
      intl.formatMessage({
        id: "onboarding_video_step_no_local_empty",
        defaultMessage:
          "Video models cannot run on this computer. Use a server instead.",
      }),
    // Nor for video.
    search: null,
  },
  audio_gen: {
    title: () =>
      intl.formatMessage({
        id: "onboarding_audio_step_title",
        defaultMessage: "Choose an audio model",
      }),
    description: () =>
      intl.formatMessage({
        id: "onboarding_audio_step_body",
        defaultMessage:
          "Creates podcasts for you. Run one on this computer, or use one from a server.",
      }),
    noLocal: () =>
      intl.formatMessage({
        id: "onboarding_audio_step_no_local_empty",
        defaultMessage:
          "Audio models cannot run on this computer. Use a server instead.",
      }),
    // Nor has audio.cpp.
    search: null,
  },
  embedding: {
    title: () =>
      intl.formatMessage({
        id: "onboarding_embedding_step_title",
        defaultMessage: "Choose an embedding model",
      }),
    description: () =>
      intl.formatMessage({
        id: "onboarding_embedding_step_body",
        defaultMessage:
          "Lets SurfSense find what you’re asking about in your documents. Choose a multilingual model only if your documents or questions are in more than one language.",
      }),
    noLocal: () =>
      intl.formatMessage({
        id: "onboarding_embedding_step_no_local_empty",
        defaultMessage: "No embedding model is on this computer.",
      }),
    // ONNX embedders, found through their own endpoints.
    search: {
      source: EMBEDDING_SEARCH,
      note: () =>
        intl.formatMessage({
          id: "onboarding_embedding_search_cost_body",
          defaultMessage:
            "Larger models make adding documents slower and use more memory.",
        }),
    },
    notice: () =>
      intl.formatMessage({
        id: "onboarding_embedding_step_fixed_body",
        defaultMessage:
          "You can’t change this later. If you’re unsure, the default works well for English.",
      }),
  },
}
