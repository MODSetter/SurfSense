import { AppBootstrap } from "@/app/app-bootstrap"
import { AccessGate } from "@/features/access/access-gate"

export function App() {
  // The Docker image asks for its password first, once it has one (ADR 0074).
  if (import.meta.env.VITE_SURFSENSE_RUNTIME === "docker") {
    return (
      <AccessGate>
        <AppBootstrap />
      </AccessGate>
    )
  }
  return <AppBootstrap />
}

export default App
