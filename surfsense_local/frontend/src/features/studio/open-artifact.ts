import { createContext, useContext } from "react"

/** Opens an artifact in Studio's viewer from elsewhere in the workspace, such
 *  as an agent step that made it. Null where no Studio is mounted. */
export const OpenArtifactContext = createContext<
  ((artifactId: number) => void) | null
>(null)

export function useOpenArtifact() {
  return useContext(OpenArtifactContext)
}
