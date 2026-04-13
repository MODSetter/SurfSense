import { useState } from "react";
import { cn } from "~/lib/utils";
import {
    TrendingUp,
    TrendingDown,
    ExternalLink,
    Filter,
    Star,
    Clock,
    DollarSign,
    Wallet,
} from "lucide-react";
import { Button } from "@/routes/ui/button";
import { ChainIcon } from "../components/shared/ChainIcon";

export interface WhaleTransaction {
    /** Transaction ID */
    id: string;
    /** Token symbol */
    tokenSymbol: string;
    /** Token name */
    tokenName?: string;
    /** Blockchain chain */
    chain: string;
    /** Transaction type */
    type: "buy" | "sell";
    /** Amount in USD */
    amountUSD: number;
    /** Amount in tokens */
    amountTokens: string;
    /** Wallet address */
    walletAddress: string;
    /** Transaction hash */
    txHash: string;
    /** When the transaction occurred */
    timestamp: Date;
    /** Whether this is a smart money wallet */
    isSmartMoney?: boolean;
    /** Whether this token is in user's watchlist */
    isInWatchlist?: boolean;
}

export interface WhaleActivityFeedProps {
    /** List of whale transactions */
    transactions: WhaleTransaction[];
    /** Callback when transaction is clicked */
    onTransactionClick?: (tx: WhaleTransaction) => void;
    /** Callback when "Track Wallet" is clicked */
    onTrackWallet?: (walletAddress: string) => void;
    /** Callback when "View on Explorer" is clicked */
    onViewExplorer?: (txHash: string, chain: string) => void;
    /** Additional class names */
    className?: string;
}

/**
 * WhaleActivityFeed - Display whale transactions (large buys/sells >$10K)
 *
 * Features:
 * - Real-time feed of large transactions
 * - Filter by watchlist tokens or all tokens
 * - Smart money wallet indicators
 * - Quick links to block explorer
 * - Track wallet functionality
 */
export function WhaleActivityFeed({
    transactions,
    onTransactionClick,
    onTrackWallet,
    onViewExplorer,
    className,
}: WhaleActivityFeedProps) {
    const [filter, setFilter] = useState<"all" | "watchlist" | "smart_money">("all");

    // Filter transactions based on selected filter
    const filteredTransactions = transactions.filter((tx) => {
        if (filter === "watchlist") return tx.isInWatchlist;
        if (filter === "smart_money") return tx.isSmartMoney;
        return true;
    });

    const formatTimeAgo = (date: Date) => {
        const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);
        if (seconds < 60) return `${seconds}s ago`;
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}m ago`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ago`;
        return `${Math.floor(hours / 24)}d ago`;
    };

    const formatAmount = (amount: number) => {
        if (amount >= 1000000) return `$${(amount / 1000000).toFixed(2)}M`;
        if (amount >= 1000) return `$${(amount / 1000).toFixed(1)}K`;
        return `$${amount.toFixed(0)}`;
    };

    const shortenAddress = (address: string) => {
        return `${address.slice(0, 6)}...${address.slice(-4)}`;
    };

    return (
        <div className={cn("flex flex-col h-full", className)}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b">
                <div className="flex items-center gap-2">
                    <div className="text-2xl">🐋</div>
                    <div>
                        <h2 className="font-semibold">Whale Activity</h2>
                        <p className="text-xs text-muted-foreground">
                            {filteredTransactions.length} transactions
                        </p>
                    </div>
                </div>
            </div>

            {/* Filter tabs */}
            <div className="flex gap-1 p-2 border-b bg-muted/30">
                <Button
                    variant={filter === "all" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setFilter("all")}
                    className="flex-1"
                >
                    All
                </Button>
                <Button
                    variant={filter === "watchlist" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setFilter("watchlist")}
                    className="flex-1"
                >
                    <Star className="h-3 w-3 mr-1" />
                    Watchlist
                </Button>
                <Button
                    variant={filter === "smart_money" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setFilter("smart_money")}
                    className="flex-1"
                >
                    Smart Money
                </Button>
            </div>

            {/* Transaction feed */}
            <div className="flex-1 overflow-y-auto">
                {filteredTransactions.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full p-8 text-center">
                        <div className="text-4xl mb-2">🐋</div>
                        <p className="text-sm text-muted-foreground">
                            No whale activity detected yet
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                            Large transactions (&gt;$10K) will appear here
                        </p>
                    </div>
                ) : (
                    <div className="divide-y">
                        {filteredTransactions.map((tx) => (
                            <div
                                key={tx.id}
                                className="p-4 hover:bg-muted/50 transition-colors cursor-pointer"
                                onClick={() => onTransactionClick?.(tx)}
                            >
                                {/* Time and smart money badge */}
                                <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                        <Clock className="h-3 w-3" />
                                        {formatTimeAgo(tx.timestamp)}
                                    </div>
                                    {tx.isSmartMoney && (
                                        <div className="flex items-center gap-1 px-2 py-0.5 bg-purple-500/10 text-purple-600 dark:text-purple-400 rounded-full text-xs font-medium">
                                            ⚠️ Smart Money
                                        </div>
                                    )}
                                </div>

                                {/* Transaction type and amount */}
                                <div className="flex items-center gap-2 mb-2">
                                    {tx.type === "buy" ? (
                                        <div className="flex items-center gap-1 text-green-600 dark:text-green-400 font-semibold">
                                            <TrendingUp className="h-4 w-4" />
                                            BUY
                                        </div>
                                    ) : (
                                        <div className="flex items-center gap-1 text-red-600 dark:text-red-400 font-semibold">
                                            <TrendingDown className="h-4 w-4" />
                                            SELL
                                        </div>
                                    )}
                                    <span className="font-bold text-lg">
                                        {formatAmount(tx.amountUSD)}
                                    </span>
                                    <span className="text-sm font-medium">
                                        {tx.tokenSymbol}
                                    </span>
                                    <ChainIcon chain={tx.chain} size="sm" />
                                </div>

                                {/* Token amount */}
                                <div className="text-xs text-muted-foreground mb-2">
                                    Amount: {tx.amountTokens} tokens
                                </div>

                                {/* Wallet address */}
                                <div className="flex items-center gap-2 mb-3">
                                    <Wallet className="h-3 w-3 text-muted-foreground" />
                                    <code className="text-xs bg-muted px-2 py-0.5 rounded">
                                        {shortenAddress(tx.walletAddress)}
                                    </code>
                                    <button
                                        className="text-xs text-primary hover:underline"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            navigator.clipboard.writeText(tx.walletAddress);
                                        }}
                                    >
                                        Copy
                                    </button>
                                </div>

                                {/* Action buttons */}
                                <div className="flex gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="flex-1 h-8 text-xs"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onViewExplorer?.(tx.txHash, tx.chain);
                                        }}
                                    >
                                        <ExternalLink className="h-3 w-3 mr-1" />
                                        Explorer
                                    </Button>
                                    {!tx.isSmartMoney && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="flex-1 h-8 text-xs"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onTrackWallet?.(tx.walletAddress);
                                            }}
                                        >
                                            <Star className="h-3 w-3 mr-1" />
                                            Track Wallet
                                        </Button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Footer info */}
            <div className="border-t p-3 bg-muted/30">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Monitoring transactions &gt;$10K</span>
                    <span>Updates every 1 min</span>
                </div>
            </div>
        </div>
    );
}
