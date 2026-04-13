import { cn } from "~/lib/utils";
import { TrendingUp, TrendingDown, Bell, Trash2, Search, Plus } from "lucide-react";
import { Button } from "@/routes/ui/button";
import { ChainIcon } from "../components/shared/ChainIcon";

export interface WatchlistItem {
    id: string;
    symbol: string;
    name?: string;
    chain: string;
    price: string;
    priceChange24h: number;
    alertCount?: number;
}

export interface WatchlistWidgetProps {
    /** List of tokens in watchlist */
    tokens: WatchlistItem[];
    /** Callback when analyze token is clicked */
    onAnalyze?: (token: WatchlistItem) => void;
    /** Callback when remove token is clicked */
    onRemove?: (tokenId: string) => void;
    /** Callback when add token is clicked */
    onAddToken?: () => void;
    /** Callback when clear all is clicked */
    onClearAll?: () => void;
    /** Additional class names */
    className?: string;
}

/**
 * WatchlistWidget - Embedded watchlist widget for chat interface
 * 
 * Displays user's watchlist inline in the chat conversation.
 * Supports quick actions like analyze, remove, and add tokens.
 */
export function WatchlistWidget({
    tokens,
    onAnalyze,
    onRemove,
    onAddToken,
    onClearAll,
    className,
}: WatchlistWidgetProps) {
    if (tokens.length === 0) {
        return (
            <div className={cn(
                "rounded-lg border bg-card p-4 my-2",
                className
            )}>
                <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">📋</span>
                    <span className="font-medium text-sm">Your Watchlist</span>
                </div>
                <div className="text-center py-4 text-muted-foreground text-sm">
                    Your watchlist is empty. Add tokens to track them!
                </div>
                <Button size="sm" variant="outline" onClick={onAddToken} className="w-full">
                    <Plus className="h-3 w-3 mr-1" />
                    Add Token
                </Button>
            </div>
        );
    }

    return (
        <div className={cn(
            "rounded-lg border bg-card p-4 my-2",
            className
        )}>
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <span className="text-lg">📋</span>
                    <span className="font-medium text-sm">WatchlistWidget</span>
                </div>
                <span className="text-xs text-muted-foreground">{tokens.length} tokens</span>
            </div>

            {/* Token list */}
            <div className="space-y-2 mb-3">
                {tokens.map((token) => (
                    <div
                        key={token.id}
                        className="flex items-center gap-3 p-2 rounded-md bg-muted/50 hover:bg-muted transition-colors"
                    >
                        {/* Token info */}
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                                <span className="font-medium text-sm">{token.symbol}</span>
                                <ChainIcon chain={token.chain} size="sm" />
                                {token.alertCount && token.alertCount > 0 && (
                                    <span className="flex items-center gap-0.5 text-xs text-primary">
                                        <Bell className="h-3 w-3" />
                                        {token.alertCount}
                                    </span>
                                )}
                            </div>
                            <p className="text-xs text-muted-foreground">{token.price}</p>
                        </div>

                        {/* Price change */}
                        <div className={cn(
                            "flex items-center gap-1 text-xs font-medium",
                            token.priceChange24h >= 0 ? "text-green-500" : "text-red-500"
                        )}>
                            {token.priceChange24h >= 0 ? (
                                <TrendingUp className="h-3 w-3" />
                            ) : (
                                <TrendingDown className="h-3 w-3" />
                            )}
                            {token.priceChange24h >= 0 ? "+" : ""}{token.priceChange24h.toFixed(1)}%
                        </div>

                        {/* Actions */}
                        <div className="flex gap-1">
                            <button
                                className="p-1 hover:bg-background rounded text-muted-foreground hover:text-foreground"
                                onClick={() => onAnalyze?.(token)}
                                title="Analyze"
                            >
                                <Search className="h-3 w-3" />
                            </button>
                            <button
                                className="p-1 hover:bg-destructive/10 rounded text-muted-foreground hover:text-destructive"
                                onClick={() => onRemove?.(token.id)}
                                title="Remove"
                            >
                                <Trash2 className="h-3 w-3" />
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            {/* Footer actions */}
            <div className="flex gap-2 pt-2 border-t">
                <Button size="sm" variant="outline" onClick={onAddToken} className="flex-1">
                    <Plus className="h-3 w-3 mr-1" />
                    Add Token
                </Button>
                {tokens.length > 0 && (
                    <Button size="sm" variant="ghost" onClick={onClearAll} className="text-destructive">
                        Clear All
                    </Button>
                )}
            </div>
        </div>
    );
}

