import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClientProvider } from "@tanstack/react-query"
import { RawIntlProvider } from "react-intl"

import "./index.css"
import App from "./App.tsx"
import { ThemeProvider } from "@/components/theme-provider.tsx"
import { Toaster } from "@/components/ui/sonner.tsx"
import { TooltipProvider } from "@/components/ui/tooltip.tsx"
import { EgressPrompt } from "@/features/egress/egress-prompt.tsx"
import { IssueReportDialog } from "@/features/feedback/issue-report-dialog.tsx"
import { MenuUpdateCheck } from "@/features/updates/menu-update-check.tsx"
import { intl } from "@/i18n/intl.ts"
import { followMainLocale } from "@/i18n/locale.ts"
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

followMainLocale()

createRoot(root).render(
  <StrictMode>
    <RawIntlProvider value={intl}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <TooltipProvider>
            <App />
            <EgressPrompt />
            <IssueReportDialog />
            <MenuUpdateCheck />
            <Toaster position="top-right" />
          </TooltipProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </RawIntlProvider>
  </StrictMode>
)
