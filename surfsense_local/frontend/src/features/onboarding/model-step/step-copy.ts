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
    /** Hugging Face search, GGUF unless a source is given. */
    search: { source?: SearchSource; note?: () => string }
    /** Said above the list, where a choice has a consequence to state. */
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
          "Finds what you ask about in your documents. Multilingual reads many languages.",
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
