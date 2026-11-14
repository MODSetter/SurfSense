import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClientProvider } from "@tanstack/react-query"
import { RawIntlProvider } from "react-intl"

import "./index.css"
import App from "./App.tsx"
import { guardFileDrops } from "@/app/file-drop-guard.ts"
import { ThemeProvider } from "@/components/theme-provider.tsx"
import { AppDialogs } from "@/components/ui/app-dialog-slot.tsx"
import { Toaster } from "@/components/ui/sonner.tsx"
import { TooltipProvider } from "@/components/ui/tooltip.tsx"
import { EgressPrompt } from "@/features/egress/egress-prompt.tsx"
import { IssueReportDialog } from "@/features/feedback/issue-report-dialog.tsx"
import { SidecarCrashReporter } from "@/features/feedback/sidecar-crash-reporter.tsx"
import { followMotionPreference } from "@/features/motion-preference/motion-preference.ts"
import { MoveProgressDialog } from "@/features/storage/move-progress-dialog.tsx"
import { followMoveProgress } from "@/features/storage/move-progress-state.ts"
import { InstallFeed } from "@/features/models/local/installs/install-feed.tsx"
import { MenuUpdateCheck } from "@/features/updates/menu-update-check.tsx"
import { intl } from "@/i18n/intl.ts"
import { followLocale } from "@/i18n/locale.ts"
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

followLocale()
followMotionPreference()
guardFileDrops(window)
followMoveProgress()

// Open over any dialog as its nested dialog, or on their own when none is open.
const APP_DIALOGS = [EgressPrompt, IssueReportDialog, MoveProgressDialog]

createRoot(root).render(
  <StrictMode>
    <RawIntlProvider value={intl}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <TooltipProvider>
            <AppDialogs dialogs={APP_DIALOGS}>
              <App />
            </AppDialogs>
            <MenuUpdateCheck />
            <InstallFeed />
            <SidecarCrashReporter />
            <Toaster position="top-right" />
          </TooltipProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </RawIntlProvider>
  </StrictMode>
)
