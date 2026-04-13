import { useState } from "react";
import { cn } from "~/lib/utils";
import { 
    Star, 
    Bell, 
    TrendingUp, 
    TrendingDown,
    Plus,
    Trash2,
    ExternalLink,
    AlertCircle
} from "lucide-react";
import { Button } from "@/routes/ui/button";
import { ChainIcon } from "../components/shared/ChainIcon";

export interface WatchlistToken {
    /** Unique identifier */
    id: string;
    /** Token symbol */
    symbol: string;
    /** Token name */
    name?: string;
    /** Blockchain chain */
    chain: string;
    /** Contract address */
    contractAddress: string;
    /** Current price */
    price: string;
    /** 24h price change percentage */
    priceChange24h: number;
    /** Whether alerts are enabled for this token */
    hasAlerts?: boolean;
    /** Number of active alerts */
    alertCount?: number;
}

export interface WatchlistAlert {
    /** Alert ID */
    id: string;
    /** Token symbol */
    tokenSymbol: string;
    /** Alert type */
    type: "price" | "volume" | "whale" | "liquidity";
    /** Alert message */
    message: string;
    /** When the alert was triggered */
    timestamp: Date;
    /** Whether alert has been read */
    isRead?: boolean;
}

export interface WatchlistPanelProps {
    /** List of watched tokens */
    tokens: WatchlistToken[];
    /** Recent alerts */
    recentAlerts?: WatchlistAlert[];
    /** Callback when token is clicked */
    onTokenClick?: (token: WatchlistToken) => void;
    /** Callback when remove token is clicked */
    onRemoveToken?: (tokenId: string) => void;
    /** Callback when add token is clicked */
    onAddToken?: () => void;
    /** Callback when configure alerts is clicked */
    onConfigureAlerts?: (token: WatchlistToken) => void;
    /** Callback when alert is clicked */
    onAlertClick?: (alert: WatchlistAlert) => void;
    /** Additional class names */
    className?: string;
}

/**
 * WatchlistPanel - Token watchlist with alerts
 * 
 * Features:
 * - List of watched tokens with price changes
 * - Alert indicators per token
 * - Recent alerts section
 * - Add/remove tokens
 * - Quick access to alert configuration
 */
export function WatchlistPanel({
    tokens,
    recentAlerts = [],
    onTokenClick,
    onRemoveToken,
    onAddToken,
    onConfigureAlerts,
    onAlertClick,
    className,
}: WatchlistPanelProps) {
    const [activeTab, setActiveTab] = useState<"tokens" | "alerts">("tokens");
    const unreadAlerts = recentAlerts.filter(a => !a.isRead).length;

    return (
        <div className={cn("flex flex-col h-full", className)}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b">
                <div className="flex items-center gap-2">
                    <Star className="h-5 w-5 text-yellow-500 fill-yellow-500" />
                    <h2 className="font-semibold">Watchlist</h2>
                </div>
                <Button size="sm" variant="outline" onClick={onAddToken}>
                    <Plus className="h-4 w-4 mr-1" />
                    Add
                </Button>
            </div>

            {/* Tabs */}
            <div className="flex border-b">
                <button
                    className={cn(
                        "flex-1 py-2 text-sm font-medium transition-colors",
                        activeTab === "tokens" 
                            ? "border-b-2 border-primary text-primary" 
                            : "text-muted-foreground hover:text-foreground"
                    )}
                    onClick={() => setActiveTab("tokens")}
                >
                    Tokens ({tokens.length})
                </button>
                <button
                    className={cn(
                        "flex-1 py-2 text-sm font-medium transition-colors relative",
                        activeTab === "alerts" 
                            ? "border-b-2 border-primary text-primary" 
                            : "text-muted-foreground hover:text-foreground"
                    )}
                    onClick={() => setActiveTab("alerts")}
                >
                    Alerts
                    {unreadAlerts > 0 && (
                        <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                            {unreadAlerts}
                        </span>
                    )}
                </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
                {activeTab === "tokens" ? (
                    <TokenList
                        tokens={tokens}
                        onTokenClick={onTokenClick}
                        onRemoveToken={onRemoveToken}
                        onConfigureAlerts={onConfigureAlerts}
                    />
                ) : (
                    <AlertList
                        alerts={recentAlerts}
                        onAlertClick={onAlertClick}
                    />
                )}
            </div>
        </div>
    );
}

/**
 * TokenList - List of watched tokens
 */
function TokenList({
    tokens,
    onTokenClick,
    onRemoveToken,
    onConfigureAlerts,
}: {
    tokens: WatchlistToken[];
    onTokenClick?: (token: WatchlistToken) => void;
    onRemoveToken?: (tokenId: string) => void;
    onConfigureAlerts?: (token: WatchlistToken) => void;
}) {
    if (tokens.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
                <Star className="h-12 w-12 text-muted-foreground/30 mb-4" />
                <p className="text-muted-foreground text-sm">No tokens in watchlist</p>
                <p className="text-muted-foreground text-xs mt-1">
                    Add tokens to track their price and set alerts
                </p>
            </div>
        );
    }

    return (
        <div className="divide-y">
            {tokens.map((token) => (
                <div
                    key={token.id}
                    className="flex items-center gap-3 p-3 hover:bg-muted/50 transition-colors cursor-pointer group"
                    onClick={() => onTokenClick?.(token)}
                >
                    {/* Token info */}
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                            <span className="font-medium truncate">{token.symbol}</span>
                            <ChainIcon chain={token.chain} size="sm" />
                            {token.hasAlerts && (
                                <Bell className="h-3 w-3 text-primary" />
                            )}
                        </div>
                        <p className="text-xs text-muted-foreground truncate">
                            {token.name || token.contractAddress.slice(0, 10) + "..."}
                        </p>
                    </div>

                    {/* Price and change */}
                    <div className="text-right">
                        <p className="font-medium text-sm">{token.price}</p>
                        <p className={cn(
                            "text-xs flex items-center justify-end gap-0.5",
                            token.priceChange24h > 0 ? "text-green-500" : "text-red-500"
                        )}>
                            {token.priceChange24h > 0 ? (
                                <TrendingUp className="h-3 w-3" />
                            ) : (
                                <TrendingDown className="h-3 w-3" />
                            )}
                            {token.priceChange24h > 0 ? "+" : ""}{token.priceChange24h.toFixed(2)}%
                        </p>
                    </div>

                    {/* Actions (visible on hover) */}
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                            className="p-1 hover:bg-muted rounded"
                            onClick={(e) => {
                                e.stopPropagation();
                                onConfigureAlerts?.(token);
                            }}
                            title="Configure alerts"
                        >
                            <Bell className="h-4 w-4 text-muted-foreground" />
                        </button>
                        <button
                            className="p-1 hover:bg-destructive/10 rounded"
                            onClick={(e) => {
                                e.stopPropagation();
                                onRemoveToken?.(token.id);
                            }}
                            title="Remove from watchlist"
                        >
                            <Trash2 className="h-4 w-4 text-destructive" />
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}

/**
 * AlertList - List of recent alerts
 */
function AlertList({
    alerts,
    onAlertClick,
}: {
    alerts: WatchlistAlert[];
    onAlertClick?: (alert: WatchlistAlert) => void;
}) {
    if (alerts.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
                <Bell className="h-12 w-12 text-muted-foreground/30 mb-4" />
                <p className="text-muted-foreground text-sm">No alerts yet</p>
                <p className="text-muted-foreground text-xs mt-1">
                    Configure alerts on your watched tokens
                </p>
            </div>
        );
    }

    const getAlertIcon = (type: WatchlistAlert["type"]) => {
        switch (type) {
            case "price": return TrendingUp;
            case "volume": return TrendingUp;
            case "whale": return AlertCircle;
            case "liquidity": return AlertCircle;
            default: return Bell;
        }
    };

    return (
        <div className="divide-y">
            {alerts.map((alert) => {
                const Icon = getAlertIcon(alert.type);
                return (
                    <div
                        key={alert.id}
                        className={cn(
                            "flex items-start gap-3 p-3 hover:bg-muted/50 transition-colors cursor-pointer",
                            !alert.isRead && "bg-primary/5"
                        )}
                        onClick={() => onAlertClick?.(alert)}
                    >
                        <div className={cn(
                            "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                            !alert.isRead ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                        )}>
                            <Icon className="h-4 w-4" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                                <span className="font-medium text-sm">{alert.tokenSymbol}</span>
                                <span className="text-xs text-muted-foreground capitalize">{alert.type}</span>
                            </div>
                            <p className="text-sm text-muted-foreground line-clamp-2">{alert.message}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                                {alert.timestamp.toLocaleTimeString()}
                            </p>
                        </div>
                        {!alert.isRead && (
                            <div className="w-2 h-2 rounded-full bg-primary flex-shrink-0 mt-2" />
                        )}
                    </div>
                );
            })}
        </div>
    );
}

