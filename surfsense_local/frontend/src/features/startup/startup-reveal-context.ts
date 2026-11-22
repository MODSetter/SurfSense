import { createContext } from "react"

// True while the dashboard's first commit is fading in over the startup frame.
export const StartupRevealContext = createContext(false)
