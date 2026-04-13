import { cn } from "~/lib/utils";
import { Activity, TrendingUp, TrendingDown, RefreshCw, ExternalLink, Droplets, BarChart3 } from "lucide-react";
import { Button } from "@/routes/ui/button";
import { ChainIcon } from "../components/shared/ChainIcon";

export interface LiveTokenDataInfo {
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
    volume6h?: number;
    volume1h?: number;
    liquidityUsd?: number;
    marketCap?: number;
    fdv?: number;
    txns24hBuys?: number;
    txns24hSells?: number;
    dex?: string;
    pairUrl?: string;
    totalPairs?: number;
    error?: string;
}

export interface LiveTokenDataWidgetProps {
    /** Live token data */
    data: LiveTokenDataInfo;
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

const formatLargeNumber = (num: number | undefined): string => {
    if (num === undefined || num === null || num === 0) return "N/A";
    if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    if (num >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
    return `$${num.toFixed(2)}`;
};

const formatNumber = (num: number | undefined): string => {
    if (num === undefined || num === null) return "0";
    return num.toLocaleString();
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
 * LiveTokenDataWidget - Displays comprehensive real-time market data
 * Used when AI fetches detailed live market information
 */
export function LiveTokenDataWidget({
    data,
    isLoading = false,
    onViewDexScreener,
    className,
}: LiveTokenDataWidgetProps) {
    const handleOpenDexScreener = () => {
        if (onViewDexScreener) {
            onViewDexScreener();
        } else if (data.pairUrl) {
            window.open(data.pairUrl, "_blank");
        } else if (data.tokenAddress) {
            window.open(`https://dexscreener.com/${data.chain}/${data.tokenAddress}`, "_blank");
        }
    };

    const totalTxns24h = (data.txns24hBuys || 0) + (data.txns24hSells || 0);
    const buyRatio = totalTxns24h > 0 ? ((data.txns24hBuys || 0) / totalTxns24h) * 100 : 50;

    return (
        <div className={cn("rounded-lg border border-purple-500/20 bg-card p-4 my-2", className)}>
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-purple-500" />
                    <span className="font-medium text-sm">Live Market Data</span>
                    {isLoading ? (
                        <span className="text-xs bg-muted px-2 py-0.5 rounded animate-pulse">Fetching...</span>
                    ) : (
                        <span className="text-xs text-purple-500 flex items-center gap-1">
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
                                        {data.priceChange24h >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
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

                    {/* Metrics Grid */}
                    <div className="grid grid-cols-2 gap-2 mb-3">
                        <div className="bg-muted/50 rounded p-2">
                            <p className="text-[10px] text-muted-foreground flex items-center gap-1">
                                <BarChart3 className="h-3 w-3" /> 24h Volume
                            </p>
                            <p className="font-medium text-sm">{formatLargeNumber(data.volume24h)}</p>
                        </div>
                        <div className="bg-muted/50 rounded p-2">
                            <p className="text-[10px] text-muted-foreground flex items-center gap-1">
                                <Droplets className="h-3 w-3" /> Liquidity
                            </p>
                            <p className="font-medium text-sm">{formatLargeNumber(data.liquidityUsd)}</p>
                        </div>
                        <div className="bg-muted/50 rounded p-2">
                            <p className="text-[10px] text-muted-foreground">Market Cap</p>
                            <p className="font-medium text-sm">{formatLargeNumber(data.marketCap)}</p>
                        </div>
                        <div className="bg-muted/50 rounded p-2">
                            <p className="text-[10px] text-muted-foreground">FDV</p>
                            <p className="font-medium text-sm">{formatLargeNumber(data.fdv)}</p>
                        </div>
                    </div>

                    {/* Transaction Activity */}
                    <div className="space-y-1 mb-3">
                        <p className="text-xs font-medium flex items-center gap-1">
                            <Activity className="h-3 w-3" /> 24h Transactions
                        </p>
                        <div className="flex items-center gap-2">
                            <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-green-500 transition-all"
                                    style={{ width: `${buyRatio}%` }}
                                />
                            </div>
                        </div>
                        <div className="flex justify-between text-[10px]">
                            <span className="text-green-500">{formatNumber(data.txns24hBuys)} buys</span>
                            <span className="text-muted-foreground">{formatNumber(totalTxns24h)} total</span>
                            <span className="text-red-500">{formatNumber(data.txns24hSells)} sells</span>
                        </div>
                    </div>

                    {/* DEX Info & Actions */}
                    <div className="flex items-center justify-between pt-2 border-t">
                        <div className="text-[10px] text-muted-foreground">
                            <span>DEX: {data.dex || "Unknown"}</span>
                            {data.totalPairs && data.totalPairs > 1 && (
                                <span className="ml-2">• {data.totalPairs} pairs</span>
                            )}
                        </div>
                        <Button variant="outline" size="sm" className="h-7 text-xs" onClick={handleOpenDexScreener}>
                            <ExternalLink className="h-3 w-3 mr-1" />
                            DexScreener
                        </Button>
                    </div>
                </>
            )}
        </div>
    );
}
