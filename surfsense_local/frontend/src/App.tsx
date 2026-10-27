import { AppBootstrap } from "@/app/app-bootstrap"
import { IN_CONTAINER } from "@/app/in-container"
import { AccessGate } from "@/features/access/access-gate"

export function App() {
  // The Docker image asks for its password first, once it has one (ADR 0074).
  if (IN_CONTAINER) {
    return (
      <AccessGate>
        <AppBootstrap />
      </AccessGate>
    )
  }
  return <AppBootstrap />
}

export default App
