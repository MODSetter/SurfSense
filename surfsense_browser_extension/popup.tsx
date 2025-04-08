import { MemoryRouter } from "react-router-dom"

import { Routing } from "~routes"
import { Toaster } from "@/routes/ui/toaster"

function IndexPopup() {
  return (
    <MemoryRouter>
      <Routing />
      <Toaster />
    </MemoryRouter>
  )
}

export default IndexPopup