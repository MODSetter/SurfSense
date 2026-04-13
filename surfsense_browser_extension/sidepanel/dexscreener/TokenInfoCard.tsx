import { useState } from "react";
import type { TokenData } from "../context/PageContextProvider";
import { Button } from "@/routes/ui/button";
import { cn } from "~/lib/utils";
import {
    TrendingUp,
    TrendingDown,
    Shield,
    Users,
    AlertTriangle,
    Star,
    Copy,
    Check
} from "lucide-react";
import { ChainIcon } from "../components/shared/ChainIcon";

export type QuickActionType = "safety" | "holders" | "predict" | "rug";

export interface EnhancedTokenData extends TokenData {
    priceChange24h?: number;
    marketCap?: string;
}

interface TokenInfoCardProps {
    tokenData: EnhancedTokenData;
    /** Whether token is in user's watchlist */
    isInWatchlist?: boolean;
    /** Callback when quick action button is clicked (generic handler) */
    onQuickAction?: (action: QuickActionType, tokenData: EnhancedTokenData) => void;
    /** Callback when watchlist button is clicked */
    onToggleWatchlist?: (tokenData: EnhancedTokenData) => void;
    /** Alternative: Direct callback for add to watchlist */
    onAddToWatchlist?: () => void;
    /** Alternative: Direct callback for safety check */
    onSafetyCheck?: () => void;
    /** Alternative: Direct callback for rug check */
    onRugCheck?: () => void;
}

/**
 * TokenInfoCard - Enhanced token info card for DexScreener pages
 *
 * Features:
 * - Price with 24h change indicator (▲/▼)
 * - Market cap display
 * - Add to watchlist button
 * - 4 quick actions: Safety, Holders, Predict, Rug Check
 * - Copy contract address
 * - Chain-specific icon
 */
export function TokenInfoCard({
    tokenData,
    isInWatchlist = false,
    onQuickAction,
    onToggleWatchlist,
    onAddToWatchlist,
    onSafetyCheck,
    onRugCheck,
}: TokenInfoCardProps) {
    const [copied, setCopied] = useState(false);

    const handleQuickAction = (action: QuickActionType) => {
        // Use specific callbacks if provided, otherwise fall back to generic handler
        if (action === "safety" && onSafetyCheck) {
            onSafetyCheck();
        } else if (action === "rug" && onRugCheck) {
            onRugCheck();
        } else if (onQuickAction) {
            onQuickAction(action, tokenData);
        } else {
            console.log("Quick action:", action, tokenData);
        }
    };

    const handleCopyAddress = async () => {
        try {
            await navigator.clipboard.writeText(tokenData.pairAddress);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error("Failed to copy address:", err);
        }
    };

    const handleToggleWatchlist = () => {
        // Use specific callback if provided, otherwise fall back to generic handler
        if (onAddToWatchlist) {
            onAddToWatchlist();
        } else if (onToggleWatchlist) {
            onToggleWatchlist(tokenData);
        }
    };

    const priceChange = tokenData.priceChange24h;
    const isPositive = priceChange !== undefined && priceChange > 0;
    const isNegative = priceChange !== undefined && priceChange < 0;

    return (
        <div className="border-b p-4 bg-muted/50">
            {/* Header with token info and watchlist */}
            <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-lg">🪙</span>
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <h3 className="font-semibold truncate">
                            {tokenData.tokenSymbol || "Unknown Token"}
                        </h3>
                        {/* Watchlist button */}
                        <button
                            onClick={handleToggleWatchlist}
                            className={cn(
                                "p-1 rounded-full transition-colors",
                                isInWatchlist
                                    ? "text-yellow-500 hover:text-yellow-600"
                                    : "text-muted-foreground hover:text-foreground"
                            )}
                            title={isInWatchlist ? "Remove from watchlist" : "Add to watchlist"}
                        >
                            <Star className={cn("h-4 w-4", isInWatchlist && "fill-current")} />
                        </button>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <ChainIcon chain={tokenData.chain} size="sm" />
                        <span>•</span>
                        <button
                            onClick={handleCopyAddress}
                            className="flex items-center gap-1 hover:text-foreground transition-colors"
                            title="Copy contract address"
                        >
                            <span>{tokenData.pairAddress.slice(0, 6)}...{tokenData.pairAddress.slice(-4)}</span>
                            {copied ? (
                                <Check className="h-3 w-3 text-green-500" />
                            ) : (
                                <Copy className="h-3 w-3" />
                            )}
                        </button>
                    </div>
                </div>
            </div>

            {/* Price with change indicator */}
            <div className="mt-3 flex items-baseline gap-2">
                <span className="text-xl font-bold">{tokenData.price || "—"}</span>
                {priceChange !== undefined && (
                    <span
                        className={cn(
                            "flex items-center gap-0.5 text-sm font-medium",
                            isPositive && "text-green-500",
                            isNegative && "text-red-500",
                            !isPositive && !isNegative && "text-muted-foreground"
                        )}
                    >
                        {isPositive && <TrendingUp className="h-3 w-3" />}
                        {isNegative && <TrendingDown className="h-3 w-3" />}
                        {isPositive ? "+" : ""}{priceChange.toFixed(2)}%
                    </span>
                )}
            </div>

            {/* Token stats grid - now with 4 columns including market cap */}
            <div className="grid grid-cols-4 gap-2 mt-3 text-sm">
                <div>
                    <span className="text-muted-foreground block text-xs">24h Vol</span>
                    <p className="font-medium truncate">{tokenData.volume24h || "—"}</p>
                </div>
                <div>
                    <span className="text-muted-foreground block text-xs">Liquidity</span>
                    <p className="font-medium truncate">{tokenData.liquidity || "—"}</p>
                </div>
                <div>
                    <span className="text-muted-foreground block text-xs">MCap</span>
                    <p className="font-medium truncate">{tokenData.marketCap || "—"}</p>
                </div>
                <div>
                    <span className="text-muted-foreground block text-xs">Chain</span>
                    <p className="font-medium capitalize truncate">{tokenData.chain}</p>
                </div>
            </div>

            {/* Quick actions - 4 buttons in grid, responsive */}
            <div className="grid grid-cols-4 gap-1 mt-3">
                <Button
                    size="sm"
                    variant="outline"
                    className="h-8 px-1.5 text-xs flex items-center justify-center"
                    onClick={() => handleQuickAction("safety")}
                >
                    <Shield className="h-3 w-3 mr-0.5 flex-shrink-0" />
                    <span className="truncate">Safety</span>
                </Button>
                <Button
                    size="sm"
                    variant="outline"
                    className="h-8 px-1.5 text-xs flex items-center justify-center"
                    onClick={() => handleQuickAction("holders")}
                >
                    <Users className="h-3 w-3 mr-0.5 flex-shrink-0" />
                    <span className="truncate">Holders</span>
                </Button>
                <Button
                    size="sm"
                    variant="outline"
                    className="h-8 px-1.5 text-xs flex items-center justify-center"
                    onClick={() => handleQuickAction("predict")}
                >
                    <TrendingUp className="h-3 w-3 mr-0.5 flex-shrink-0" />
                    <span className="truncate">Predict</span>
                </Button>
                <Button
                    size="sm"
                    variant="outline"
                    className="h-8 px-1.5 text-xs flex items-center justify-center text-orange-600 hover:text-orange-700 hover:bg-orange-50 dark:text-orange-400 dark:hover:bg-orange-950"
                    onClick={() => handleQuickAction("rug")}
                >
                    <AlertTriangle className="h-3 w-3 mr-0.5 flex-shrink-0" />
                    <span className="truncate">Rug</span>
                </Button>
            </div>
        </div>
    );
}
