import { useEffect, useState, useCallback } from "react";
import { Storage } from "@plasmohq/storage";

export interface ContextAction {
    action: string;
    text: string;
    pageUrl?: string;
    linkUrl?: string;
    timestamp: number;
}

/**
 * Hook to handle context menu actions from background script
 * Returns pending action and a function to clear it
 */
export function useContextAction() {
    const [pendingAction, setPendingAction] = useState<ContextAction | null>(null);

    // Check for pending context action on mount and when sidepanel gains focus
    const checkPendingAction = useCallback(async () => {
        const storage = new Storage({ area: "local" });
        const action = await storage.get<ContextAction>("pendingContextAction");
        
        if (action && action.timestamp) {
            // Only process actions from last 30 seconds
            const isRecent = Date.now() - action.timestamp < 30000;
            if (isRecent) {
                setPendingAction(action);
                // Clear the pending action
                await storage.remove("pendingContextAction");
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
 * Generate chat message based on context action
 */
export function getMessageForAction(action: ContextAction): string | null {
    const text = action.text;
    
    switch (action.action) {
        case "analyze-token":
            return `Analyze token: ${text}`;
        case "check-safety":
            return `Is ${text} safe? Check for rug pull risks.`;
        case "add-watchlist":
            return `Add ${text} to my watchlist`;
        case "copy-address":
            // This is handled differently - just copy to clipboard
            if (text) {
                navigator.clipboard.writeText(text);
            }
            return null;
        case "view-explorer":
            // Detect chain and open explorer
            if (text.startsWith("0x") && text.length === 42) {
                // Ethereum address
                window.open(`https://etherscan.io/address/${text}`, "_blank");
            } else if (text.length >= 32 && text.length <= 44) {
                // Solana address
                window.open(`https://solscan.io/account/${text}`, "_blank");
            }
            return null;
        case "capture-page":
            return "Capture this page to my knowledge base";
        case "ask-ai-page":
            return "What is this page about? Summarize the key information.";
        default:
            return null;
    }
}

