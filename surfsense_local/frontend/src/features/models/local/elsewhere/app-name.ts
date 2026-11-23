import { intl } from "@/i18n/intl"

// Product names stay as their makers write them. The codes are `App` in the
// backend's modules/llm/catalog/local/engines/llamacpp/elsewhere/places.py.
const PRODUCTS: Record<string, string> = {
  ollama: "Ollama",
  lm_studio: "LM Studio",
  llama_cpp: "llama.cpp",
  jan: "Jan",
  gpt4all: "GPT4All",
}

/** Whose folder a model was found in, as a person would name it. */
export function appName(app: string): string {
  if (Object.hasOwn(PRODUCTS, app)) return PRODUCTS[app]
  if (app === "hugging_face") {
    return intl.formatMessage({
      id: "models_elsewhere_hugging_face_label",
      defaultMessage: "Hugging Face cache",
    })
  }
  return intl.formatMessage({
    id: "models_elsewhere_folder_label",
    defaultMessage: "Your folder",
  })
}
