import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClientProvider } from "@tanstack/react-query"

import "./index.css"
import App from "./App.tsx"
import { ThemeProvider } from "@/components/theme-provider.tsx"
import { Toaster } from "@/components/ui/sonner.tsx"
import { TooltipProvider } from "@/components/ui/tooltip.tsx"
import { queryClient } from "@/lib/query-client.ts"

const root = document.getElementById("root")
if (!root) {
  throw new Error("Missing application root")
}

if (window.surfsense?.platform) {
  document.documentElement.classList.add("electron")
  if (window.surfsense.platform === "darwin") {
    document.documentElement.classList.add("electron-macos")
  }
}

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TooltipProvider>
          <App />
          <Toaster position="top-right" />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>
)
