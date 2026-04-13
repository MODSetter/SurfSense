import { useState } from "react";
import { cn } from "~/lib/utils";
import {
    TrendingUp,
    TrendingDown,
    Wallet,
    Plus,
    BarChart3,
    ExternalLink,
    RefreshCw,
    Star,
    Bell,
    Eye,
} from "lucide-react";
import { Button } from "@/routes/ui/button";
import { ChainIcon } from "../components/shared/ChainIcon";

export interface PortfolioHolding {
    tokenAddress: string;
    chain: string;
    symbol: string;
    name: string;
    amount: string;
    currentPrice: number;
    currentValue: number;
    change24h: number;
    change24hPercent: number;
    entryPrice?: number;
    pnl?: number;
    pnlPercent?: number;
}

export interface PortfolioAnalytics {
    bestPerformer: { symbol: string; change: number };
    worstPerformer: { symbol: string; change: number };
    winRate: number;
    avgHoldTime: number;
    totalTrades: number;
}

export interface PortfolioData {
    wallets: {
        address: string;
        chain: string;
        type: "metamask" | "phantom" | "coinbase";
    }[];
    
    totalValue: number;
    change24h: number;
    change24hPercent: number;
    
    holdings: PortfolioHolding[];
    analytics: PortfolioAnalytics;
}

export interface PortfolioPanelProps {
    /** Portfolio data */
    portfolio: PortfolioData;
    /** Callback when refresh is clicked */
    onRefresh?: () => void;
    /** Callback when "Analyze" is clicked for a token */
    onAnalyzeToken?: (holding: PortfolioHolding) => void;
    /** Callback when "Set Alert" is clicked for a token */
    onSetAlert?: (holding: PortfolioHolding) => void;
    /** Callback when "View on DexScreener" is clicked */
    onViewToken?: (holding: PortfolioHolding) => void;
    /** Callback when "Add Manual Position" is clicked */
    onAddPosition?: () => void;
    /** Whether data is loading */
    isLoading?: boolean;
    /** Additional class names */
    className?: string;
}

/**
 * PortfolioPanel - Portfolio tracker with holdings and P&L
 *
 * Features:
 * - Total portfolio value and 24h change
 * - List of holdings with current value and P&L
 * - Performance analytics (best/worst performers, win rate)
 * - Quick actions per token (analyze, alert, view)
 * - Manual position entry
 */
export function PortfolioPanel({
    portfolio,
    onRefresh,
    onAnalyzeToken,
    onSetAlert,
    onViewToken,
    onAddPosition,
    isLoading = false,
    className,
}: PortfolioPanelProps) {
    const [isRefreshing, setIsRefreshing] = useState(false);

    const handleRefresh = async () => {
        setIsRefreshing(true);
        await onRefresh?.();
        setTimeout(() => setIsRefreshing(false), 1000);
    };

    const formatCurrency = (value: number) => {
        if (value >= 1000000) return `$${(value / 1000000).toFixed(2)}M`;
        if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`;
        return `$${value.toFixed(2)}`;
    };

    const formatPercent = (value: number) => {
        const sign = value >= 0 ? "+" : "";
        return `${sign}${value.toFixed(2)}%`;
    };

    return (
        <div className={cn("flex flex-col h-full", className)}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b">
                <div className="flex items-center gap-2">
                    <Wallet className="h-5 w-5 text-primary" />
                    <div>
                        <h2 className="font-semibold">Portfolio</h2>
                        <p className="text-xs text-muted-foreground">
                            {portfolio.holdings.length} tokens
                        </p>
                    </div>
                </div>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={handleRefresh}
                    disabled={isRefreshing}
                >
                    <RefreshCw className={cn("h-4 w-4", isRefreshing && "animate-spin")} />
                </Button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
                {/* Total Value */}
                <div className="p-4 border-b bg-muted/30">
                    <div className="text-xs text-muted-foreground mb-1">Total Value</div>
                    <div className="flex items-baseline gap-2 mb-2">
                        <span className="font-bold text-3xl">{formatCurrency(portfolio.totalValue)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className={cn(
                            "font-semibold text-sm",
                            portfolio.change24hPercent >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
                        )}>
                            {formatPercent(portfolio.change24hPercent)}
                        </span>
                        <span className="text-xs text-muted-foreground">
                            ({portfolio.change24h >= 0 ? "+" : ""}{formatCurrency(portfolio.change24h)}) 24h
                        </span>
                        {portfolio.change24hPercent >= 0 ? (
                            <TrendingUp className="h-4 w-4 text-green-600" />
                        ) : (
                            <TrendingDown className="h-4 w-4 text-red-600" />
                        )}
                    </div>
                </div>

                {/* Holdings List */}
                <div className="divide-y">
                    {portfolio.holdings.map((holding) => (
                        <div key={`${holding.chain}-${holding.tokenAddress}`} className="p-4 hover:bg-muted/50 transition-colors">
                            {/* Token Info */}
                            <div className="flex items-start justify-between mb-2">
                                <div className="flex items-center gap-2">
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold">{holding.symbol}</span>
                                            <ChainIcon chain={holding.chain} size="xs" />
                                        </div>
                                        <div className="text-xs text-muted-foreground">{holding.name}</div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="font-semibold">{formatCurrency(holding.currentValue)}</div>
                                    <div className={cn(
                                        "text-xs font-medium",
                                        holding.change24hPercent >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
                                    )}>
                                        {formatPercent(holding.change24hPercent)}
                                    </div>
                                </div>
                            </div>

                            {/* Amount and Price */}
                            <div className="flex items-center justify-between text-xs text-muted-foreground mb-3">
                                <span>{holding.amount} tokens</span>
                                <span>${holding.currentPrice.toFixed(6)}</span>
                            </div>

                            {/* P&L (if available) */}
                            {holding.pnl !== undefined && holding.pnlPercent !== undefined && (
                                <div className="flex items-center justify-between mb-3 p-2 bg-muted/50 rounded">
                                    <span className="text-xs text-muted-foreground">P&L</span>
                                    <div className="flex items-center gap-2">
                                        <span className={cn(
                                            "text-xs font-semibold",
                                            holding.pnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
                                        )}>
                                            {holding.pnl >= 0 ? "+" : ""}{formatCurrency(holding.pnl)}
                                        </span>
                                        <span className={cn(
                                            "text-xs font-medium",
                                            holding.pnlPercent >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
                                        )}>
                                            ({formatPercent(holding.pnlPercent)})
                                        </span>
                                    </div>
                                </div>
                            )}

                            {/* Action Buttons */}
                            <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="flex-1 h-8 text-xs"
                                    onClick={() => onAnalyzeToken?.(holding)}
                                >
                                    <BarChart3 className="h-3 w-3 mr-1" />
                                    Analyze
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="flex-1 h-8 text-xs"
                                    onClick={() => onSetAlert?.(holding)}
                                >
                                    <Bell className="h-3 w-3 mr-1" />
                                    Alert
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="h-8 w-8 p-0"
                                    onClick={() => onViewToken?.(holding)}
                                >
                                    <Eye className="h-3 w-3" />
                                </Button>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Add Position Button */}
                <div className="p-4 border-t">
                    <Button
                        variant="outline"
                        className="w-full"
                        onClick={onAddPosition}
                    >
                        <Plus className="h-4 w-4 mr-2" />
                        Add Manual Position
                    </Button>
                </div>

                {/* Performance Analytics */}
                <div className="p-4 border-t bg-muted/30">
                    <h3 className="font-semibold text-sm mb-3">Performance</h3>
                    <div className="space-y-2">
                        <div className="flex items-center justify-between p-2 bg-background rounded">
                            <span className="text-xs text-muted-foreground">Best Performer</span>
                            <span className="text-xs font-semibold text-green-600 dark:text-green-400">
                                {portfolio.analytics.bestPerformer.symbol} (+{portfolio.analytics.bestPerformer.change.toFixed(1)}%)
                            </span>
                        </div>
                        <div className="flex items-center justify-between p-2 bg-background rounded">
                            <span className="text-xs text-muted-foreground">Worst Performer</span>
                            <span className="text-xs font-semibold text-red-600 dark:text-red-400">
                                {portfolio.analytics.worstPerformer.symbol} ({portfolio.analytics.worstPerformer.change.toFixed(1)}%)
                            </span>
                        </div>
                        <div className="flex items-center justify-between p-2 bg-background rounded">
                            <span className="text-xs text-muted-foreground">Win Rate</span>
                            <span className="text-xs font-semibold">{portfolio.analytics.winRate}%</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
