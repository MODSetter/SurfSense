import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { getHealth } from "@/lib/api"

type ApiState = "checking" | "up" | "down"

export function App() {
  const [api, setApi] = useState<ApiState>("checking")

  useEffect(() => {
    const controller = new AbortController()

    getHealth(controller.signal)
      .then(() => setApi("up"))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setApi("down")
          console.error(error)
        }
      })

    return () => controller.abort()
  }, [])

  return (
    <div className="flex min-h-svh flex-col gap-4 p-6">
      <h1 className="font-medium">SurfSense Community Local</h1>
      {api === "checking" ? (
        <Skeleton className="h-6 w-24" />
      ) : (
        <Badge variant={api === "up" ? "secondary" : "destructive"}>
          API {api}
        </Badge>
      )}
    </div>
  )
}

export default App
