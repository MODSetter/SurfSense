import { useQuery } from "@tanstack/react-query"

import { requestJson } from "@/lib/api"

import { MODELS_QUERY_KEY } from "../models-query"

/** Which chosen model takes a picture in. Null: a change to a picture is drawn
 *  again from its prompt, by the image model. */
export type PicturesIn = { source: "edit_model" | "image_model" | null }

/** Under the models key, so choosing a model reads it again. */
export function usePicturesIn({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    enabled,
    queryKey: [...MODELS_QUERY_KEY, "pictures-in"],
    queryFn: ({ signal }) =>
      requestJson<PicturesIn>("/llm/pictures-in", { signal }),
  })
}
