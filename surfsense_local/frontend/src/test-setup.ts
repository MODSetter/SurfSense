// jsdom has no Web Animations API; Base UI calls it to wait for exit animations.
Element.prototype.getAnimations ??= () => []
// Nor pointer capture, which sonner takes when a toast is pressed, to swipe it away.
Element.prototype.setPointerCapture ??= () => {}

// Replies in progress live at module level, one set per window; each test is a
// fresh window, so none inherits another's runs.
import { afterEach } from "vitest"

import { resetChatRuns } from "@/features/chat/runs/run-store"

afterEach(() => resetChatRuns())
