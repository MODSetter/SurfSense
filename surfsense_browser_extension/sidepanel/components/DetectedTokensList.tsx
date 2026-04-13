import { Coins, ExternalLink } from "lucide-react";
import { Button } from "@/routes/ui/button";
import { cn } from "~/lib/utils";
import type { TokenData } from "../context/PageContextProvider";
import { ChainIcon } from "./shared/ChainIcon";

export interface DetectedTokensListProps {
    /** List of detected tokens */
    tokens: TokenData[];
    /** Callback when a token is clicked */
    onTokenClick?: (token: TokenData) => void;
    /** Additional class names */
    className?: string;
}

/**
 * DetectedTokensList - Display list of tokens detected from page content
 * 
 * Features:
 * - Shows tokens detected from Twitter mentions, contract addresses, trading pairs
 * - Click to analyze token
 * - Shows chain icon for each token
 */
export function DetectedTokensList({
    tokens,
    onTokenClick,
    className,
}: DetectedTokensListProps) {
    if (tokens.length === 0) {
        return null;
    }

    return (
        <div className={cn("border-b bg-muted/30", className)}>
            <div className="p-3">
                <div className="flex items-center gap-2 mb-2">
                    <Coins className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold">Detected Tokens</h3>
                    <span className="text-xs text-muted-foreground">
                        ({tokens.length} found)
                    </span>
                </div>
                
                <div className="space-y-1">
                    {tokens.slice(0, 5).map((token, index) => (
                        <button
                            key={index}
                            onClick={() => onTokenClick?.(token)}
                            className="w-full flex items-center justify-between p-2 rounded-md hover:bg-background transition-colors text-left"
                        >
                            <div className="flex items-center gap-2 flex-1 min-w-0">
                                <ChainIcon chain={token.chain} size="sm" />
                                <div className="flex-1 min-w-0">
                                    {token.tokenSymbol ? (
                                        <div className="font-medium text-sm truncate">
                                            {token.tokenSymbol}
                                        </div>
                                    ) : (
                                        <div className="text-xs text-muted-foreground font-mono truncate">
                                            {token.pairAddress.slice(0, 8)}...{token.pairAddress.slice(-6)}
                                        </div>
                                    )}
                                    {token.tokenName && (
                                        <div className="text-xs text-muted-foreground truncate">
                                            {token.tokenName}
                                        </div>
                                    )}
                                </div>
                            </div>
                            <ExternalLink className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                        </button>
                    ))}
                </div>
                
                {tokens.length > 5 && (
                    <div className="text-xs text-muted-foreground text-center mt-2">
                        +{tokens.length - 5} more tokens detected
                    </div>
                )}
            </div>
        </div>
    );
}

