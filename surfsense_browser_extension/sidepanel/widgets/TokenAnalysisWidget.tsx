import { cn } from "~/lib/utils";
import { Shield, TrendingUp, TrendingDown, Users, AlertTriangle, CheckCircle, Star, Bell } from "lucide-react";
import { Button } from "@/routes/ui/button";
import { ChainIcon } from "../components/shared/ChainIcon";

export interface TokenAnalysisData {
    /** Token symbol */
    symbol: string;
    /** Token name */
    name?: string;
    /** Blockchain */
    chain: string;
    /** Current price */
    price: string;
    /** 24h price change */
    priceChange24h: number;
    /** Market cap */
    marketCap?: string;
    /** 24h volume */
    volume24h?: string;
    /** Liquidity */
    liquidity?: string;
    /** Safety score (0-100) */
    safetyScore?: number;
    /** Holder count */
    holderCount?: number;
    /** Top 10 holder percentage */
    top10HolderPercent?: number;
}

export interface TokenAnalysisWidgetProps {
    /** Token analysis data */
    data: TokenAnalysisData;
    /** Whether token is in watchlist */
    isInWatchlist?: boolean;
    /** Callback when add to watchlist is clicked */
    onAddToWatchlist?: () => void;
    /** Callback when set alert is clicked */
    onSetAlert?: () => void;
    /** Callback when analyze further is clicked */
    onAnalyzeFurther?: () => void;
    /** Additional class names */
    className?: string;
}

/**
 * TokenAnalysisWidget - Full token analysis card embedded in chat
 * 
 * Displays comprehensive token analysis including price, safety score,
 * and key metrics. Used when AI responds to token research queries.
 */
export function TokenAnalysisWidget({
    data,
    isInWatchlist = false,
    onAddToWatchlist,
    onSetAlert,
    onAnalyzeFurther,
    className,
}: TokenAnalysisWidgetProps) {
    const getSafetyColor = (score?: number) => {
        if (!score) return "text-muted-foreground";
        if (score >= 80) return "text-green-500";
        if (score >= 60) return "text-yellow-500";
        return "text-red-500";
    };

    const getSafetyLabel = (score?: number) => {
        if (!score) return "Unknown";
        if (score >= 80) return "Low Risk";
        if (score >= 60) return "Medium Risk";
        return "High Risk";
    };

    return (
        <div className={cn(
            "rounded-lg border bg-card p-4 my-2",
            className
        )}>
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <span className="text-lg">📊</span>
                    <span className="font-medium text-sm">TokenAnalysisCard</span>
                </div>
                <ChainIcon chain={data.chain} size="sm" />
            </div>

            {/* Token info */}
            <div className="flex items-center gap-3 mb-3 pb-3 border-b">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                    <span className="text-lg">🪙</span>
                </div>
                <div className="flex-1">
                    <div className="flex items-center gap-2">
                        <span className="font-bold">{data.symbol}</span>
                        {data.name && (
                            <span className="text-xs text-muted-foreground">{data.name}</span>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="font-medium">{data.price}</span>
                        <span className={cn(
                            "flex items-center gap-0.5 text-sm",
                            data.priceChange24h >= 0 ? "text-green-500" : "text-red-500"
                        )}>
                            {data.priceChange24h >= 0 ? (
                                <TrendingUp className="h-3 w-3" />
                            ) : (
                                <TrendingDown className="h-3 w-3" />
                            )}
                            {data.priceChange24h >= 0 ? "+" : ""}{data.priceChange24h.toFixed(1)}%
                        </span>
                    </div>
                </div>
                <button
                    onClick={onAddToWatchlist}
                    className={cn(
                        "p-2 rounded-full transition-colors",
                        isInWatchlist
                            ? "text-yellow-500 bg-yellow-500/10"
                            : "text-muted-foreground hover:text-yellow-500 hover:bg-yellow-500/10"
                    )}
                >
                    <Star className={cn("h-5 w-5", isInWatchlist && "fill-current")} />
                </button>
            </div>

            {/* Metrics grid */}
            <div className="grid grid-cols-2 gap-2 mb-3 text-sm">
                {data.marketCap && (
                    <div className="bg-muted/50 rounded p-2">
                        <p className="text-xs text-muted-foreground">Market Cap</p>
                        <p className="font-medium">{data.marketCap}</p>
                    </div>
                )}
                {data.volume24h && (
                    <div className="bg-muted/50 rounded p-2">
                        <p className="text-xs text-muted-foreground">24h Volume</p>
                        <p className="font-medium">{data.volume24h}</p>
                    </div>
                )}
                {data.liquidity && (
                    <div className="bg-muted/50 rounded p-2">
                        <p className="text-xs text-muted-foreground">Liquidity</p>
                        <p className="font-medium">{data.liquidity}</p>
                    </div>
                )}
                {data.safetyScore !== undefined && (
                    <div className="bg-muted/50 rounded p-2">
                        <p className="text-xs text-muted-foreground">Safety Score</p>
                        <p className={cn("font-medium flex items-center gap-1", getSafetyColor(data.safetyScore))}>
                            <Shield className="h-3 w-3" />
                            {data.safetyScore}/100 ({getSafetyLabel(data.safetyScore)})
                        </p>
                    </div>
                )}
            </div>

            {/* Holder info */}
            {(data.holderCount || data.top10HolderPercent) && (
                <div className="flex items-center gap-4 mb-3 text-xs text-muted-foreground">
                    {data.holderCount && (
                        <span className="flex items-center gap-1">
                            <Users className="h-3 w-3" />
                            {data.holderCount.toLocaleString()} holders
                        </span>
                    )}
                    {data.top10HolderPercent && (
                        <span className={cn(
                            "flex items-center gap-1",
                            data.top10HolderPercent > 50 ? "text-yellow-500" : ""
                        )}>
                            {data.top10HolderPercent > 50 && <AlertTriangle className="h-3 w-3" />}
                            Top 10: {data.top10HolderPercent}%
                        </span>
                    )}
                </div>
            )}

            {/* Action buttons */}
            <div className="flex gap-1.5 flex-wrap">
                <Button size="sm" variant="outline" onClick={onAddToWatchlist} className="flex-1 min-w-0 text-xs h-8">
                    <Star className="h-3 w-3 mr-1 flex-shrink-0" />
                    <span className="truncate">{isInWatchlist ? "In Watchlist" : "Add to Watchlist"}</span>
                </Button>
                <Button size="sm" variant="outline" onClick={onSetAlert} className="h-8 w-8 p-0 flex-shrink-0">
                    <Bell className="h-3 w-3" />
                </Button>
                <Button size="sm" variant="default" onClick={onAnalyzeFurther} className="text-xs h-8">
                    Analyze More
                </Button>
            </div>
        </div>
    );
}

