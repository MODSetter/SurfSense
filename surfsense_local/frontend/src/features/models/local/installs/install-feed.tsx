import { useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { retainInstallFeed } from "./feed"

/** Mounted once for the app, so a download's end is heard with Settings closed. */
export function InstallFeed() {
  const client = useQueryClient()
  useEffect(() => retainInstallFeed(client), [client])
  return null
}
