import { cn } from "~/lib/utils";
import { Globe, TrendingUp, TrendingDown } from "lucide-react";

export interface MarketToken {
    symbol: string;
    name: string;
    price: number;
    priceChange24h: number;
    marketCap?: number;
    volume24h?: number;
}

export interface MarketOverviewData {
    tokens: MarketToken[];
    totalMarketCap?: number;
    totalVolume24h?: number;
    btcDominance?: number;
    fearGreedIndex?: number;
}

export interface MarketOverviewWidgetProps {
    /** Market overview data */
    data: MarketOverviewData;
    /** Callback when token is clicked */
    onTokenClick?: (token: MarketToken) => void;
    /** Additional class names */
    className?: string;
}

const formatPrice = (price: number): string => {
    if (price < 1) return `$${price.toFixed(4)}`;
    return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatLargeNumber = (num: number): string => {
    if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
    if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    return `$${num.toFixed(2)}`;
};

const getFearGreedLabel = (index: number): string => {
    if (index > 75) return "Extreme Greed";
    if (index > 50) return "Greed";
    if (index > 25) return "Fear";
    return "Extreme Fear";
};

/**
 * MarketOverviewWidget - Displays market overview inline in chat
 * Used when AI responds to "show market overview" or "how's the market?"
 */
export function MarketOverviewWidget({
    data,
    onTokenClick,
    className,
}: MarketOverviewWidgetProps) {
    return (
        <div className={cn("rounded-lg border bg-card p-4 my-2", className)}>
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <Globe className="h-5 w-5 text-blue-500" />
                <span className="font-medium text-sm">Market Overview</span>
            </div>

            {/* Global Stats */}
            {(data.totalMarketCap || data.btcDominance || data.fearGreedIndex) && (
                <div className="grid grid-cols-2 gap-2 mb-3">
                    {data.totalMarketCap && (
                        <div className="bg-muted/50 rounded p-2">
                            <p className="text-xs text-muted-foreground">Total Market Cap</p>
                            <p className="font-medium text-sm">{formatLargeNumber(data.totalMarketCap)}</p>
                        </div>
                    )}
                    {data.totalVolume24h && (
                        <div className="bg-muted/50 rounded p-2">
                            <p className="text-xs text-muted-foreground">24h Volume</p>
                            <p className="font-medium text-sm">{formatLargeNumber(data.totalVolume24h)}</p>
                        </div>
                    )}
                    {data.btcDominance && (
                        <div className="bg-muted/50 rounded p-2">
                            <p className="text-xs text-muted-foreground">BTC Dominance</p>
                            <p className="font-medium text-sm">{data.btcDominance.toFixed(1)}%</p>
                        </div>
                    )}
                    {data.fearGreedIndex && (
                        <div className={cn(
                            "rounded p-2",
                            data.fearGreedIndex > 50 ? "bg-green-500/10" : "bg-red-500/10"
                        )}>
                            <p className="text-xs text-muted-foreground">Fear & Greed</p>
                            <p className={cn(
                                "font-medium text-sm",
                                data.fearGreedIndex > 50 ? "text-green-500" : "text-red-500"
                            )}>
                                {data.fearGreedIndex} - {getFearGreedLabel(data.fearGreedIndex)}
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* Token Prices */}
            <div className="space-y-2">
                {data.tokens.map((token) => (
                    <div
                        key={token.symbol}
                        className="bg-muted/50 rounded p-3 flex items-center justify-between hover:bg-muted/70 cursor-pointer transition-colors"
                        onClick={() => onTokenClick?.(token)}
                    >
                        <div>
                            <p className="font-bold">{token.symbol}</p>
                            <p className="text-xs text-muted-foreground">{token.name}</p>
                        </div>
                        <div className="text-right">
                            <p className="font-medium">{formatPrice(token.price)}</p>
                            <p className={cn(
                                "text-xs flex items-center justify-end gap-0.5",
                                token.priceChange24h >= 0 ? "text-green-500" : "text-red-500"
                            )}>
                                {token.priceChange24h >= 0 ? (
                                    <TrendingUp className="h-3 w-3" />
                                ) : (
                                    <TrendingDown className="h-3 w-3" />
                                )}
                                {token.priceChange24h >= 0 ? "+" : ""}{token.priceChange24h.toFixed(2)}%
                            </p>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

