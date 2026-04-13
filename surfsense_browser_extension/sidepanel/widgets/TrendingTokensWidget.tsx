import { cn } from "~/lib/utils";
import { Flame, TrendingUp, TrendingDown, Star } from "lucide-react";
import { Button } from "@/routes/ui/button";
import { ChainIcon } from "../components/shared/ChainIcon";

export interface TrendingToken {
    symbol: string;
    name: string;
    chain: string;
    contractAddress?: string;
    price: number;
    priceChange24h: number;
    priceChange1h?: number;
    volume24h?: number;
    liquidity?: number;
    rank?: number;
}

export interface TrendingTokensWidgetProps {
    /** List of trending tokens */
    tokens: TrendingToken[];
    /** Filter by chain (optional) */
    chain?: string;
    /** Timeframe for trending data */
    timeframe?: string;
    /** Callback when token is clicked */
    onTokenClick?: (token: TrendingToken) => void;
    /** Callback when add to watchlist is clicked */
    onAddToWatchlist?: (token: TrendingToken) => void;
    /** Additional class names */
    className?: string;
}

const formatPrice = (price: number): string => {
    if (price < 0.00001) return `$${price.toExponential(2)}`;
    if (price < 1) return `$${price.toFixed(6)}`;
    return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatLargeNumber = (num: number): string => {
    if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    if (num >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
    return `$${num.toFixed(2)}`;
};

/**
 * TrendingTokensWidget - Displays trending/hot tokens inline in chat
 * Used when AI responds to "what's hot on Solana?" or "show trending tokens"
 */
export function TrendingTokensWidget({
    tokens,
    chain = "All Chains",
    timeframe = "24h",
    onTokenClick,
    onAddToWatchlist,
    className,
}: TrendingTokensWidgetProps) {
    return (
        <div className={cn("rounded-lg border bg-card p-4 my-2", className)}>
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <Flame className="h-5 w-5 text-orange-500" />
                    <span className="font-medium text-sm">Trending on {chain}</span>
                    <span className="text-xs bg-muted px-2 py-0.5 rounded">{timeframe}</span>
                </div>
            </div>

            {/* Token List */}
            {tokens.length === 0 ? (
                <p className="text-muted-foreground text-center py-4 text-sm">No trending tokens found</p>
            ) : (
                <div className="divide-y">
                    {tokens.map((token, index) => (
                        <div
                            key={token.symbol + index}
                            className="flex items-center justify-between py-2.5 hover:bg-muted/50 -mx-2 px-2 rounded cursor-pointer transition-colors"
                            onClick={() => onTokenClick?.(token)}
                        >
                            <div className="flex items-center gap-2">
                                <span className="text-sm font-bold text-muted-foreground w-5">
                                    #{token.rank || index + 1}
                                </span>
                                <ChainIcon chain={token.chain} size="xs" />
                                <div>
                                    <div className="flex items-center gap-1">
                                        <span className="font-medium text-sm">{token.symbol}</span>
                                    </div>
                                    <span className="text-xs text-muted-foreground">{token.name}</span>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="text-right">
                                    <p className="font-medium text-sm">{formatPrice(token.price)}</p>
                                    <p className={cn(
                                        "text-xs flex items-center justify-end gap-0.5",
                                        token.priceChange24h >= 0 ? "text-green-500" : "text-red-500"
                                    )}>
                                        {token.priceChange24h >= 0 ? (
                                            <TrendingUp className="h-3 w-3" />
                                        ) : (
                                            <TrendingDown className="h-3 w-3" />
                                        )}
                                        {token.priceChange24h >= 0 ? "+" : ""}{token.priceChange24h.toFixed(1)}%
                                    </p>
                                </div>
                                {token.volume24h && (
                                    <div className="text-right hidden sm:block">
                                        <p className="text-xs text-muted-foreground">Vol</p>
                                        <p className="text-xs">{formatLargeNumber(token.volume24h)}</p>
                                    </div>
                                )}
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onAddToWatchlist?.(token);
                                    }}
                                >
                                    <Star className="h-3.5 w-3.5" />
                                </Button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

