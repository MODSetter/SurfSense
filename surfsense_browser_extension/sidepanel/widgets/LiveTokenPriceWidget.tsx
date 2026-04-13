import { cn } from "~/lib/utils";
import { Zap, TrendingUp, TrendingDown, RefreshCw, ExternalLink } from "lucide-react";
import { Button } from "@/routes/ui/button";
import { ChainIcon } from "../components/shared/ChainIcon";

export interface LiveTokenPriceData {
    chain: string;
    tokenAddress: string;
    tokenSymbol?: string;
    tokenName?: string;
    priceUsd?: string;
    priceNative?: string;
    priceChange5m?: number;
    priceChange1h?: number;
    priceChange6h?: number;
    priceChange24h?: number;
    volume24h?: number;
    liquidityUsd?: number;
    marketCap?: number;
    fdv?: number;
    dex?: string;
    pairUrl?: string;
    error?: string;
}

export interface LiveTokenPriceWidgetProps {
    /** Live token price data */
    data: LiveTokenPriceData;
    /** Whether data is loading */
    isLoading?: boolean;
    /** Callback when view on DexScreener is clicked */
    onViewDexScreener?: () => void;
    /** Additional class names */
    className?: string;
}

const formatPrice = (price: string | undefined): string => {
    if (!price || price === "N/A") return "N/A";
    const num = parseFloat(price);
    if (isNaN(num)) return price;
    if (num < 0.00001) return `$${num.toExponential(2)}`;
    if (num < 1) return `$${num.toFixed(6)}`;
    return `$${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const PriceChange = ({ value, label }: { value: number | undefined; label: string }) => {
    if (value === undefined || value === null) return null;
    const isPositive = value >= 0;
    return (
        <div className="text-center">
            <p className="text-[10px] text-muted-foreground">{label}</p>
            <p className={cn("text-xs font-medium", isPositive ? "text-green-500" : "text-red-500")}>
                {isPositive ? "+" : ""}{value.toFixed(2)}%
            </p>
        </div>
    );
};

/**
 * LiveTokenPriceWidget - Displays real-time token price inline in chat
 * Used when AI fetches current/live price data
 */
export function LiveTokenPriceWidget({
    data,
    isLoading = false,
    onViewDexScreener,
    className,
}: LiveTokenPriceWidgetProps) {
    const handleOpenDexScreener = () => {
        if (onViewDexScreener) {
            onViewDexScreener();
        } else if (data.pairUrl) {
            window.open(data.pairUrl, "_blank");
        } else if (data.tokenAddress) {
            window.open(`https://dexscreener.com/${data.chain}/${data.tokenAddress}`, "_blank");
        }
    };

    return (
        <div className={cn("rounded-lg border border-blue-500/20 bg-card p-4 my-2", className)}>
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <Zap className="h-4 w-4 text-blue-500" />
                    <span className="font-medium text-sm">Live Price</span>
                    {isLoading ? (
                        <span className="text-xs bg-muted px-2 py-0.5 rounded animate-pulse">Fetching...</span>
                    ) : (
                        <span className="text-xs text-blue-500 flex items-center gap-1">
                            <RefreshCw className="h-3 w-3" />
                            Real-time
                        </span>
                    )}
                </div>
            </div>

            {data.error ? (
                <div className="text-red-500 text-xs p-2 bg-red-500/10 rounded">
                    ⚠️ {data.error}
                </div>
            ) : (
                <>
                    {/* Token Header */}
                    <div className="flex items-center gap-3 mb-3">
                        <ChainIcon chain={data.chain} size="sm" />
                        <div className="flex-1">
                            <div className="flex items-center gap-2">
                                <span className="font-bold">{data.tokenSymbol || "Token"}</span>
                                {data.tokenName && (
                                    <span className="text-xs text-muted-foreground">{data.tokenName}</span>
                                )}
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="font-semibold text-lg">{formatPrice(data.priceUsd)}</span>
                                {data.priceChange24h !== undefined && (
                                    <span className={cn(
                                        "flex items-center gap-0.5 text-xs font-medium",
                                        data.priceChange24h >= 0 ? "text-green-500" : "text-red-500"
                                    )}>
                                        {data.priceChange24h >= 0 ? (
                                            <TrendingUp className="h-3 w-3" />
                                        ) : (
                                            <TrendingDown className="h-3 w-3" />
                                        )}
                                        {data.priceChange24h >= 0 ? "+" : ""}{data.priceChange24h.toFixed(2)}%
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Price Changes */}
                    <div className="flex justify-around py-2 bg-muted/30 rounded mb-3">
                        <PriceChange value={data.priceChange5m} label="5m" />
                        <PriceChange value={data.priceChange1h} label="1h" />
                        <PriceChange value={data.priceChange6h} label="6h" />
                        <PriceChange value={data.priceChange24h} label="24h" />
                    </div>

                    {/* Action */}
                    <Button
                        variant="outline"
                        size="sm"
                        className="w-full text-xs"
                        onClick={handleOpenDexScreener}
                    >
                        <ExternalLink className="h-3 w-3 mr-1" />
                        View on DexScreener
                    </Button>
                </>
            )}
        </div>
    );
}

