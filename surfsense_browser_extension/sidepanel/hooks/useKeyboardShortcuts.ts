import { useEffect, useState, useCallback } from "react";
import { Storage } from "@plasmohq/storage";

export interface KeyboardAction {
    action: string;
    timestamp: number;
}

/**
 * Hook to handle keyboard shortcut actions from background script
 * Returns pending action and a function to clear it
 * 
 * Keyboard shortcuts defined in manifest:
 * - open-sidepanel: Ctrl+Shift+S (just opens panel, no message)
 * - analyze-token: Ctrl+Shift+A
 * - add-watchlist: Ctrl+Shift+W
 * - capture-page: Ctrl+Shift+C
 * - show-portfolio: Ctrl+Shift+P
 */
export function useKeyboardShortcuts() {
    const [pendingAction, setPendingAction] = useState<KeyboardAction | null>(null);

    // Check for pending keyboard action on mount and when sidepanel gains focus
    const checkPendingAction = useCallback(async () => {
        const storage = new Storage({ area: "local" });
        const action = await storage.get<KeyboardAction>("pendingKeyboardAction");
        
        if (action && action.timestamp) {
            // Only process actions from last 30 seconds
            const isRecent = Date.now() - action.timestamp < 30000;
            if (isRecent) {
                setPendingAction(action);
                // Clear the pending action
                await storage.remove("pendingKeyboardAction");
            }
        }
    }, []);

    useEffect(() => {
        // Check on mount
        checkPendingAction();

        // Check when window gains focus (sidepanel opened)
        const handleFocus = () => {
            checkPendingAction();
        };

        window.addEventListener("focus", handleFocus);
        
        // Also listen for visibility change
        const handleVisibilityChange = () => {
            if (document.visibilityState === "visible") {
                checkPendingAction();
            }
        };
        document.addEventListener("visibilitychange", handleVisibilityChange);

        return () => {
            window.removeEventListener("focus", handleFocus);
            document.removeEventListener("visibilitychange", handleVisibilityChange);
        };
    }, [checkPendingAction]);

    const clearAction = useCallback(() => {
        setPendingAction(null);
    }, []);

    return { pendingAction, clearAction, checkPendingAction };
}

/**
 * Generate chat message based on keyboard shortcut action
 * Returns null for actions that don't need a chat message (like open-sidepanel)
 */
export function getMessageForKeyboardAction(action: KeyboardAction): string | null {
    switch (action.action) {
        case "open-sidepanel":
            // Just opens the panel, no message needed
            return null;
        case "analyze-token":
            return "Analyze the current token on this page";
        case "add-watchlist":
            return "Add the current token to my watchlist";
        case "capture-page":
            return "Capture this page to my knowledge base";
        case "show-portfolio":
            return "Show my portfolio";
        default:
            return null;
    }
}

