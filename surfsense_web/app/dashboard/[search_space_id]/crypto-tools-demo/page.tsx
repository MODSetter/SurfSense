"use client";

import { cn } from "@/lib/utils";
import { Shield, TrendingUp, TrendingDown, Users, AlertTriangle, Star, Bell, ExternalLink, Trash2, Plus, Activity, Zap, CheckCircle, Eye, Settings, Edit2, Percent, DollarSign, X, Flame, Fish, ArrowUpRight, ArrowDownRight, Globe, Wallet, User as UserIcon, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { ChainIcon } from "@/components/crypto/ChainIcon";
import { SafetyBadge } from "@/components/crypto/SafetyBadge";

// ============ MOCK DATA ============
const MOCK_TOKEN_ANALYSIS = {
    symbol: "BULLA",
    name: "Bulla Token",
    chain: "solana",
    contractAddress: "BULLAxK9xGJxGqPwPqTbGpLd9yKthvfNUet9V8wj8rWD",
    price: 0.00001234,
    priceChange24h: 156.7,
    marketCap: 2100000,
    volume24h: 1200000,
    liquidity: 450000,
    safetyScore: 72,
    holderCount: 12500,
    top10HolderPercent: 45,
};

const MOCK_WATCHLIST = [
    { id: "1", symbol: "BULLA", name: "Bulla Token", chain: "solana", price: 0.00001234, priceChange24h: 156.7, alertCount: 2 },
    { id: "2", symbol: "SOL", name: "Solana", chain: "solana", price: 98.45, priceChange24h: 3.2, alertCount: 1 },
    { id: "3", symbol: "BONK", name: "Bonk", chain: "solana", price: 0.00002156, priceChange24h: -12.5, alertCount: 0 },
    { id: "4", symbol: "WIF", name: "dogwifhat", chain: "solana", price: 2.34, priceChange24h: -5.8, alertCount: 3 },
];

const MOCK_ALERTS = [
    { id: "1", type: "price_above" as const, value: 0.00002, enabled: true },
    { id: "2", type: "price_below" as const, value: 0.000008, enabled: true },
    { id: "3", type: "percent_change" as const, value: 20, enabled: false },
    { id: "4", type: "whale_activity" as const, value: 50000, enabled: true },
];

const MOCK_PROACTIVE_ALERT = {
    alertType: "price_surge" as const,
    tokenSymbol: "BULLA",
    tokenName: "Bulla Token",
    value: 0.00001234,
    previousValue: 0.00000482,
    message: "BULLA just surged 156% in the last hour! This is unusual activity - consider taking profits or setting a stop-loss.",
    severity: "warning" as const,
    timestamp: "2 min ago",
};

const MOCK_ACTION_CONFIRMATION = {
    actionType: "watchlist_add" as const,
    tokenSymbol: "BULLA",
    details: ["Price alerts (±10%)", "Whale activity monitoring", "Safety score changes"],
};

// ============ HELPER FUNCTIONS ============
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

// ============ DEMO COMPONENTS ============

// 1. Token Analysis Demo
function TokenAnalysisDemo() {
    const args = MOCK_TOKEN_ANALYSIS;
    return (
        <Card className="overflow-hidden">
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                    <span>📊</span>
                    Token Analysis
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <ChainIcon chain={args.chain} size="md" />
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="font-bold text-lg">{args.symbol}</span>
                                <span className="text-muted-foreground text-sm">{args.name}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="font-medium">{formatPrice(args.price)}</span>
                                <span className={cn("flex items-center gap-0.5 text-sm font-medium", args.priceChange24h >= 0 ? "text-green-500" : "text-red-500")}>
                                    {args.priceChange24h >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                                    {args.priceChange24h >= 0 ? "+" : ""}{args.priceChange24h.toFixed(2)}%
                                </span>
                            </div>
                        </div>
                    </div>
                    <SafetyBadge score={args.safetyScore} size="lg" />
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="bg-muted/50 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Market Cap</p>
                        <p className="font-medium">{formatLargeNumber(args.marketCap)}</p>
                    </div>
                    <div className="bg-muted/50 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">24h Volume</p>
                        <p className="font-medium">{formatLargeNumber(args.volume24h)}</p>
                    </div>
                    <div className="bg-muted/50 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Liquidity</p>
                        <p className="font-medium">{formatLargeNumber(args.liquidity)}</p>
                    </div>
                    <div className="bg-muted/50 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Holders</p>
                        <p className="font-medium flex items-center gap-1">
                            <Users className="h-3 w-3" />
                            {args.holderCount.toLocaleString()}
                        </p>
                    </div>
                </div>
                {args.top10HolderPercent > 50 && (
                    <div className="flex items-center gap-2 text-yellow-600 dark:text-yellow-400 text-sm bg-yellow-500/10 rounded-lg p-2">
                        <AlertTriangle className="h-4 w-4" />
                        <span>Top 10 holders own {args.top10HolderPercent}% of supply - high concentration risk</span>
                    </div>
                )}
                <div className="flex gap-2 pt-2">
                    <Button variant="outline" size="sm" className="flex-1">
                        <Star className="h-4 w-4 mr-2" />Add to Watchlist
                    </Button>
                    <Button variant="outline" size="sm"><Bell className="h-4 w-4" /></Button>
                    <Button variant="outline" size="sm"><ExternalLink className="h-4 w-4" /></Button>
                </div>
            </CardContent>
        </Card>
    );
}

// 2. Watchlist Display Demo
function WatchlistDisplayDemo() {
    const tokens = MOCK_WATCHLIST;
    const sortedByChange = [...tokens].sort((a, b) => b.priceChange24h - a.priceChange24h);
    const bestPerformer = sortedByChange[0];
    const worstPerformer = sortedByChange[sortedByChange.length - 1];

    return (
        <Card className="overflow-hidden">
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Star className="h-5 w-5 text-yellow-500" />
                        Your Watchlist
                        <Badge variant="secondary">{tokens.length}</Badge>
                    </div>
                    <Button variant="outline" size="sm"><Plus className="h-4 w-4 mr-1" />Add Token</Button>
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
                <div className="divide-y">
                    {tokens.map((token) => (
                        <div key={token.id} className="flex items-center justify-between py-3 hover:bg-muted/50 -mx-2 px-2 rounded cursor-pointer transition-colors">
                            <div className="flex items-center gap-3">
                                <ChainIcon chain={token.chain} size="sm" />
                                <div>
                                    <div className="flex items-center gap-2">
                                        <span className="font-medium">{token.symbol}</span>
                                        {token.alertCount > 0 && (
                                            <Badge variant="outline" className="text-xs px-1.5 py-0">
                                                <Bell className="h-2.5 w-2.5 mr-0.5" />{token.alertCount}
                                            </Badge>
                                        )}
                                    </div>
                                    <span className="text-xs text-muted-foreground">{token.name}</span>
                                </div>
                            </div>
                            <div className="flex items-center gap-4">
                                <div className="text-right">
                                    <p className="font-medium">{formatPrice(token.price)}</p>
                                    <p className={cn("text-sm flex items-center justify-end gap-0.5", token.priceChange24h >= 0 ? "text-green-500" : "text-red-500")}>
                                        {token.priceChange24h >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                                        {token.priceChange24h >= 0 ? "+" : ""}{token.priceChange24h.toFixed(1)}%
                                    </p>
                                </div>
                                <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-red-500">
                                    <Trash2 className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                    ))}
                </div>
                <div className="pt-3 border-t text-sm text-muted-foreground">
                    <span className="text-green-500 font-medium">{bestPerformer.symbol}</span> is your best performer (+{bestPerformer.priceChange24h.toFixed(1)}%)
                    {worstPerformer.priceChange24h < 0 && (
                        <span> • <span className="text-red-500 font-medium">{worstPerformer.symbol}</span> needs attention ({worstPerformer.priceChange24h.toFixed(1)}%)</span>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}

// 3. Action Confirmation Demo
function ActionConfirmationDemo() {
    const args = MOCK_ACTION_CONFIRMATION;
    return (
        <Card className="overflow-hidden border-l-4 border-l-green-500">
            <CardContent className="py-4">
                <div className="flex items-start gap-3">
                    <div className="p-2 rounded-full bg-yellow-500/10">
                        <CheckCircle className="h-5 w-5 text-green-500" />
                    </div>
                    <div className="flex-1">
                        <div className="flex items-center gap-2">
                            <Star className="h-4 w-4 text-yellow-500" />
                            <span className="font-medium">Added to Watchlist</span>
                            <Badge variant="secondary" className="font-mono">{args.tokenSymbol}</Badge>
                        </div>
                        <div className="mt-2 text-sm text-muted-foreground">
                            <p className="mb-1">Default monitoring enabled:</p>
                            <ul className="list-disc list-inside space-y-0.5">
                                {args.details.map((detail, i) => (<li key={i}>{detail}</li>))}
                            </ul>
                        </div>
                    </div>
                </div>
                <div className="flex gap-2 mt-4 ml-11">
                    <Button variant="outline" size="sm"><Eye className="h-3 w-3 mr-1" />View Watchlist</Button>
                    <Button variant="outline" size="sm"><Settings className="h-3 w-3 mr-1" />Edit Alerts</Button>
                </div>
            </CardContent>
        </Card>
    );
}

// 4. Alert Configuration Demo
const ALERT_TYPE_CONFIG = {
    price_above: { icon: TrendingUp, label: "Price Above", color: "text-green-500" },
    price_below: { icon: TrendingDown, label: "Price Below", color: "text-red-500" },
    percent_change: { icon: Percent, label: "% Change", color: "text-blue-500" },
    volume_spike: { icon: Activity, label: "Volume Spike", color: "text-purple-500" },
    whale_activity: { icon: DollarSign, label: "Whale Activity", color: "text-orange-500" },
};

const formatAlertValue = (type: string, value: number): string => {
    if (type === "percent_change") return `${value > 0 ? "+" : ""}${value}%`;
    if (type === "volume_spike") return `${value}x normal`;
    if (type === "whale_activity") return `>${value.toLocaleString()} USD`;
    return `$${value < 1 ? value.toFixed(6) : value.toLocaleString()}`;
};

function AlertConfigurationDemo() {
    const alerts = MOCK_ALERTS;
    const enabledCount = alerts.filter(a => a.enabled).length;

    return (
        <Card className="overflow-hidden">
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Bell className="h-5 w-5 text-blue-500" />
                        Alerts for BULLA
                        <Badge variant="secondary">{enabledCount} active</Badge>
                    </div>
                    <Button variant="outline" size="sm"><Bell className="h-4 w-4 mr-1" />Add Alert</Button>
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
                <div className="divide-y">
                    {alerts.map((alert) => {
                        const config = ALERT_TYPE_CONFIG[alert.type];
                        const Icon = config.icon;
                        return (
                            <div key={alert.id} className="flex items-center justify-between py-3">
                                <div className="flex items-center gap-3">
                                    <Icon className={cn("h-4 w-4", config.color)} />
                                    <div>
                                        <p className="font-medium">{config.label}</p>
                                        <p className="text-sm text-muted-foreground">{formatAlertValue(alert.type, alert.value)}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Switch checked={alert.enabled} />
                                    <Button variant="ghost" size="icon" className="h-8 w-8"><Edit2 className="h-3 w-3" /></Button>
                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-red-500"><Trash2 className="h-3 w-3" /></Button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </CardContent>
        </Card>
    );
}

// 5. Proactive Alert Demo
function ProactiveAlertDemo() {
    const args = MOCK_PROACTIVE_ALERT;
    const change = ((args.value - args.previousValue) / args.previousValue) * 100;

    return (
        <Card className="overflow-hidden border-l-4 border-l-green-500">
            <CardContent className="py-4">
                <div className="flex items-start gap-3">
                    <div className="p-2 rounded-full bg-green-500/10">
                        <TrendingUp className="h-5 w-5 text-green-500" />
                    </div>
                    <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                            <Badge variant="secondary" className="uppercase text-xs">PRICE SURGE</Badge>
                            <span className="font-bold">{args.tokenSymbol}</span>
                            <span className="font-medium text-green-500">+{change.toFixed(1)}%</span>
                            <span className="text-xs text-muted-foreground ml-auto">{args.timestamp}</span>
                        </div>
                        <p className="mt-2 text-sm">{args.message}</p>
                    </div>
                    <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground"><X className="h-4 w-4" /></Button>
                </div>
                <div className="flex gap-2 mt-3 ml-11">
                    <Button variant="outline" size="sm"><Eye className="h-3 w-3 mr-1" />View Details</Button>
                    <Button variant="outline" size="sm"><Bell className="h-3 w-3 mr-1" />Adjust Alert</Button>
                </div>
            </CardContent>
        </Card>
    );
}

// 6. Trending Tokens Demo
const MOCK_TRENDING = [
    { symbol: "BULLA", name: "Bulla Token", chain: "solana", price: 0.00001234, priceChange24h: 156.7, volume24h: 1200000, rank: 1 },
    { symbol: "POPCAT", name: "Popcat", chain: "solana", price: 0.89, priceChange24h: 45.2, volume24h: 8500000, rank: 2 },
    { symbol: "WIF", name: "dogwifhat", chain: "solana", price: 2.34, priceChange24h: 32.1, volume24h: 15000000, rank: 3 },
    { symbol: "BONK", name: "Bonk", chain: "solana", price: 0.00002156, priceChange24h: 18.5, volume24h: 5200000, rank: 4 },
];

function TrendingTokensDemo() {
    return (
        <Card className="overflow-hidden">
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                    <Flame className="h-5 w-5 text-orange-500" />
                    Trending on Solana
                    <Badge variant="secondary">24h</Badge>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="divide-y">
                    {MOCK_TRENDING.map((token) => (
                        <div key={token.symbol} className="flex items-center justify-between py-3 hover:bg-muted/50 -mx-2 px-2 rounded cursor-pointer">
                            <div className="flex items-center gap-3">
                                <span className="text-lg font-bold text-muted-foreground w-6">#{token.rank}</span>
                                <ChainIcon chain={token.chain} size="sm" />
                                <div>
                                    <span className="font-medium">{token.symbol}</span>
                                    <p className="text-xs text-muted-foreground">{token.name}</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-4">
                                <div className="text-right">
                                    <p className="font-medium">{formatPrice(token.price)}</p>
                                    <p className={cn("text-sm", token.priceChange24h >= 0 ? "text-green-500" : "text-red-500")}>
                                        +{token.priceChange24h.toFixed(1)}%
                                    </p>
                                </div>
                                <div className="text-right hidden md:block">
                                    <p className="text-xs text-muted-foreground">Volume</p>
                                    <p className="text-sm">{formatLargeNumber(token.volume24h)}</p>
                                </div>
                                <Button variant="ghost" size="icon" className="h-8 w-8"><Star className="h-4 w-4" /></Button>
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// 7. Whale Activity Demo
const MOCK_WHALE_TXS = [
    { id: "1", type: "buy" as const, amountUsd: 250000, walletLabel: "Smart Money 1", timestamp: "5m ago" },
    { id: "2", type: "sell" as const, amountUsd: 180000, walletLabel: "Whale #42", timestamp: "12m ago" },
    { id: "3", type: "buy" as const, amountUsd: 320000, walletLabel: null, timestamp: "25m ago" },
    { id: "4", type: "transfer" as const, amountUsd: 500000, walletLabel: "Exchange Hot Wallet", timestamp: "1h ago" },
];

function WhaleActivityDemo() {
    const summary = { totalBuyVolume: 570000, totalSellVolume: 180000, netFlow: 390000, uniqueWhales: 4 };
    return (
        <Card className="overflow-hidden">
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Fish className="h-5 w-5 text-blue-500" />
                        Whale Activity - BULLA
                    </div>
                    <ChainIcon chain="solana" size="sm" />
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="bg-green-500/10 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Buy Volume</p>
                        <p className="font-medium text-green-500">{formatLargeNumber(summary.totalBuyVolume)}</p>
                    </div>
                    <div className="bg-red-500/10 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Sell Volume</p>
                        <p className="font-medium text-red-500">{formatLargeNumber(summary.totalSellVolume)}</p>
                    </div>
                    <div className="bg-green-500/10 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Net Flow</p>
                        <p className="font-medium text-green-500">+{formatLargeNumber(summary.netFlow)}</p>
                    </div>
                    <div className="bg-muted/50 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Unique Whales</p>
                        <p className="font-medium">{summary.uniqueWhales}</p>
                    </div>
                </div>
                <div className="divide-y">
                    {MOCK_WHALE_TXS.map((tx) => (
                        <div key={tx.id} className="flex items-center justify-between py-3">
                            <div className="flex items-center gap-3">
                                <div className={cn("p-2 rounded-full", tx.type === "buy" ? "bg-green-500/10" : tx.type === "sell" ? "bg-red-500/10" : "bg-muted")}>
                                    {tx.type === "buy" ? <ArrowUpRight className="h-4 w-4 text-green-500" /> : tx.type === "sell" ? <ArrowDownRight className="h-4 w-4 text-red-500" /> : <ArrowUpRight className="h-4 w-4" />}
                                </div>
                                <div>
                                    <span className={cn("font-medium capitalize", tx.type === "buy" ? "text-green-500" : tx.type === "sell" ? "text-red-500" : "")}>{tx.type}</span>
                                    <span className="font-medium ml-2">{formatLargeNumber(tx.amountUsd)}</span>
                                    <p className="text-xs text-muted-foreground">{tx.walletLabel || "Unknown Wallet"} • {tx.timestamp}</p>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// 8. Market Overview Demo
const MOCK_MARKET = [
    { symbol: "BTC", name: "Bitcoin", price: 67500, priceChange24h: 2.3 },
    { symbol: "ETH", name: "Ethereum", price: 3450, priceChange24h: -1.2 },
    { symbol: "SOL", name: "Solana", price: 98.45, priceChange24h: 5.7 },
];

function MarketOverviewDemo() {
    return (
        <Card className="overflow-hidden">
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                    <Globe className="h-5 w-5 text-blue-500" />
                    Market Overview
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="bg-muted/50 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Total Market Cap</p>
                        <p className="font-medium">$2.45T</p>
                    </div>
                    <div className="bg-muted/50 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">24h Volume</p>
                        <p className="font-medium">$89.2B</p>
                    </div>
                    <div className="bg-muted/50 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">BTC Dominance</p>
                        <p className="font-medium">52.3%</p>
                    </div>
                    <div className="bg-green-500/10 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Fear & Greed</p>
                        <p className="font-medium text-green-500">72 - Greed</p>
                    </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {MOCK_MARKET.map((token) => (
                        <div key={token.symbol} className="bg-muted/50 rounded-lg p-4 flex items-center justify-between">
                            <div>
                                <p className="font-bold text-lg">{token.symbol}</p>
                                <p className="text-xs text-muted-foreground">{token.name}</p>
                            </div>
                            <div className="text-right">
                                <p className="font-medium">${token.price.toLocaleString()}</p>
                                <p className={cn("text-sm", token.priceChange24h >= 0 ? "text-green-500" : "text-red-500")}>
                                    {token.priceChange24h >= 0 ? "+" : ""}{token.priceChange24h.toFixed(2)}%
                                </p>
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// 9. Holder Analysis Demo
const MOCK_HOLDERS = [
    { rank: 1, address: "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1", label: "Raydium LP", percentage: 15.2, balance: 152000000 },
    { rank: 2, address: "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM", label: null, percentage: 8.5, balance: 85000000 },
    { rank: 3, address: "HN7cABqLq46Es1jh92dQQisAq662SmxELLLsHHe4YWrH", label: "Team Wallet", percentage: 7.2, balance: 72000000 },
];

function HolderAnalysisDemo() {
    return (
        <Card className="overflow-hidden">
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Users className="h-5 w-5 text-purple-500" />
                        Holder Analysis - BULLA
                    </div>
                    <ChainIcon chain="solana" size="sm" />
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="bg-muted/50 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Total Holders</p>
                        <p className="font-medium">12,500</p>
                    </div>
                    <div className="bg-red-500/10 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Top 10 Hold</p>
                        <p className="font-medium text-red-500">45.2%</p>
                    </div>
                    <div className="bg-muted/50 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Top 50 Hold</p>
                        <p className="font-medium">68.5%</p>
                    </div>
                    <div className="bg-yellow-500/10 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground">Concentration Risk</p>
                        <p className="font-medium text-yellow-500">Medium</p>
                    </div>
                </div>
                <div className="divide-y">
                    {MOCK_HOLDERS.map((holder) => (
                        <div key={holder.rank} className="flex items-center justify-between py-2">
                            <div className="flex items-center gap-3">
                                <span className="text-sm font-bold text-muted-foreground w-6">#{holder.rank}</span>
                                <div>
                                    <p className="font-medium text-sm">{holder.label || `${holder.address.slice(0, 6)}...${holder.address.slice(-4)}`}</p>
                                </div>
                            </div>
                            <div className="text-right">
                                <p className="font-medium text-sm">{holder.percentage.toFixed(2)}%</p>
                                <p className="text-xs text-muted-foreground">{(holder.balance / 1e6).toFixed(1)}M</p>
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// 10. Portfolio Display Demo
const MOCK_PORTFOLIO_HOLDINGS = [
    { symbol: "SOL", name: "Solana", chain: "solana", balance: 50, value: 4922.5, pnlPercent: 125.5, allocation: 45 },
    { symbol: "BULLA", name: "Bulla Token", chain: "solana", balance: 5000000, value: 61.7, pnlPercent: 256.7, allocation: 5.6 },
    { symbol: "ETH", name: "Ethereum", chain: "ethereum", balance: 1.5, value: 5175, pnlPercent: 45.2, allocation: 47.3 },
];

function PortfolioDisplayDemo() {
    return (
        <Card className="overflow-hidden">
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                    <Wallet className="h-5 w-5 text-emerald-500" />
                    Your Portfolio
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="bg-gradient-to-r from-emerald-500/10 to-blue-500/10 rounded-lg p-4">
                    <p className="text-sm text-muted-foreground">Total Value</p>
                    <p className="text-3xl font-bold">$10,934.20</p>
                    <p className="text-sm text-green-500 flex items-center gap-1 mt-1">
                        <TrendingUp className="h-4 w-4" />+$3,245.80 (+42.3%)
                    </p>
                </div>
                <div className="divide-y">
                    {MOCK_PORTFOLIO_HOLDINGS.map((holding) => (
                        <div key={holding.symbol} className="flex items-center justify-between py-3">
                            <div className="flex items-center gap-3">
                                <ChainIcon chain={holding.chain} size="sm" />
                                <div>
                                    <div className="flex items-center gap-2">
                                        <span className="font-medium">{holding.symbol}</span>
                                        <Badge variant="secondary" className="text-xs">{holding.allocation.toFixed(1)}%</Badge>
                                    </div>
                                    <span className="text-xs text-muted-foreground">{holding.balance.toLocaleString()} tokens</span>
                                </div>
                            </div>
                            <div className="text-right">
                                <p className="font-medium">${holding.value.toLocaleString()}</p>
                                <p className={cn("text-sm", holding.pnlPercent >= 0 ? "text-green-500" : "text-red-500")}>
                                    +{holding.pnlPercent.toFixed(2)}%
                                </p>
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// 11. User Profile Demo
function UserProfileDemo() {
    return (
        <Card className="overflow-hidden">
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                    <UserIcon className="h-5 w-5 text-indigo-500" />
                    Your Investment Profile
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded-lg p-4 border text-yellow-500 bg-yellow-500/10 border-yellow-500/20">
                        <div className="flex items-center gap-2 mb-2">
                            <Shield className="h-4 w-4" />
                            <span className="text-sm font-medium">Risk Tolerance</span>
                        </div>
                        <p className="text-lg font-bold">Moderate</p>
                        <p className="text-xs text-muted-foreground mt-1">Balance between risk and reward</p>
                    </div>
                    <div className="rounded-lg p-4 border bg-muted/50">
                        <div className="flex items-center gap-2 mb-2">
                            <Target className="h-4 w-4" />
                            <span className="text-sm font-medium">Investment Style</span>
                        </div>
                        <p className="text-lg font-bold">Swing Trader</p>
                        <p className="text-xs text-muted-foreground mt-1">Hold for days to weeks</p>
                    </div>
                </div>
                <div>
                    <p className="text-sm font-medium text-muted-foreground mb-2">Preferred Chains</p>
                    <div className="flex flex-wrap gap-2">
                        <Badge variant="default">Solana</Badge>
                        <Badge variant="default">Ethereum</Badge>
                        <Badge variant="outline">Base</Badge>
                    </div>
                </div>
                <p className="text-xs text-muted-foreground text-center pt-2">
                    Say "update my risk tolerance to aggressive" to change settings
                </p>
            </CardContent>
        </Card>
    );
}

export default function CryptoToolsDemoPage() {
    return (
        <div className="container mx-auto py-8 px-4 max-w-4xl">
            <div className="mb-8">
                <h1 className="text-3xl font-bold mb-2">🧪 Crypto Tools Demo</h1>
                <p className="text-muted-foreground">Preview of all crypto tool UI components with mock data</p>
                <p className="text-sm text-muted-foreground mt-2">These components render inline in chat when AI calls the corresponding tools.</p>
            </div>
            <div className="space-y-8">
                <section>
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <span className="bg-blue-500/10 text-blue-500 px-2 py-1 rounded text-sm">1</span>
                        Token Analysis <code className="text-xs bg-muted px-2 py-1 rounded ml-2">analyze_token</code>
                    </h2>
                    <p className="text-sm text-muted-foreground mb-3">Triggered by: "Analyze BULLA", "Is BULLA safe?", "Research this token"</p>
                    <TokenAnalysisDemo />
                </section>
                <section>
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <span className="bg-blue-500/10 text-blue-500 px-2 py-1 rounded text-sm">2</span>
                        Watchlist Display <code className="text-xs bg-muted px-2 py-1 rounded ml-2">show_watchlist</code>
                    </h2>
                    <p className="text-sm text-muted-foreground mb-3">Triggered by: "Show my watchlist", "What tokens am I tracking?"</p>
                    <WatchlistDisplayDemo />
                </section>
                <section>
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <span className="bg-blue-500/10 text-blue-500 px-2 py-1 rounded text-sm">3</span>
                        Action Confirmation <code className="text-xs bg-muted px-2 py-1 rounded ml-2">confirm_action</code>
                    </h2>
                    <p className="text-sm text-muted-foreground mb-3">Triggered by: "Add BULLA to watchlist", "Remove SOL from watchlist"</p>
                    <ActionConfirmationDemo />
                </section>
                <section>
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <span className="bg-blue-500/10 text-blue-500 px-2 py-1 rounded text-sm">4</span>
                        Alert Configuration <code className="text-xs bg-muted px-2 py-1 rounded ml-2">configure_alerts</code>
                    </h2>
                    <p className="text-sm text-muted-foreground mb-3">Triggered by: "Show my alerts for BULLA", "Set alert if BULLA drops 20%"</p>
                    <AlertConfigurationDemo />
                </section>
                <section>
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <span className="bg-blue-500/10 text-blue-500 px-2 py-1 rounded text-sm">5</span>
                        Proactive Alert <code className="text-xs bg-muted px-2 py-1 rounded ml-2">proactive_alert</code>
                    </h2>
                    <p className="text-sm text-muted-foreground mb-3">AI-initiated: Automatically sent when price surges, whale activity detected, etc.</p>
                    <ProactiveAlertDemo />
                </section>
                <section>
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <span className="bg-orange-500/10 text-orange-500 px-2 py-1 rounded text-sm">6</span>
                        Trending Tokens <code className="text-xs bg-muted px-2 py-1 rounded ml-2">get_trending_tokens</code>
                    </h2>
                    <p className="text-sm text-muted-foreground mb-3">Triggered by: "What's hot on Solana?", "Show trending tokens", "What's pumping today?"</p>
                    <TrendingTokensDemo />
                </section>
                <section>
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <span className="bg-orange-500/10 text-orange-500 px-2 py-1 rounded text-sm">7</span>
                        Whale Activity <code className="text-xs bg-muted px-2 py-1 rounded ml-2">get_whale_activity</code>
                    </h2>
                    <p className="text-sm text-muted-foreground mb-3">Triggered by: "Show whale activity for BULLA", "Any big buys?", "Who's accumulating?"</p>
                    <WhaleActivityDemo />
                </section>
                <section>
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <span className="bg-orange-500/10 text-orange-500 px-2 py-1 rounded text-sm">8</span>
                        Market Overview <code className="text-xs bg-muted px-2 py-1 rounded ml-2">get_market_overview</code>
                    </h2>
                    <p className="text-sm text-muted-foreground mb-3">Triggered by: "How's the market?", "Show market overview", "What's the sentiment?"</p>
                    <MarketOverviewDemo />
                </section>
                <section>
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <span className="bg-orange-500/10 text-orange-500 px-2 py-1 rounded text-sm">9</span>
                        Holder Analysis <code className="text-xs bg-muted px-2 py-1 rounded ml-2">analyze_holders</code>
                    </h2>
                    <p className="text-sm text-muted-foreground mb-3">Triggered by: "Who holds BULLA?", "Show holder distribution", "Is it concentrated?"</p>
                    <HolderAnalysisDemo />
                </section>
                <section>
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <span className="bg-orange-500/10 text-orange-500 px-2 py-1 rounded text-sm">10</span>
                        Portfolio Display <code className="text-xs bg-muted px-2 py-1 rounded ml-2">get_portfolio</code>
                    </h2>
                    <p className="text-sm text-muted-foreground mb-3">Triggered by: "How's my portfolio?", "Show my holdings", "What's my P&L?"</p>
                    <PortfolioDisplayDemo />
                </section>
                <section>
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <span className="bg-orange-500/10 text-orange-500 px-2 py-1 rounded text-sm">11</span>
                        User Profile <code className="text-xs bg-muted px-2 py-1 rounded ml-2">get_user_profile</code>
                    </h2>
                    <p className="text-sm text-muted-foreground mb-3">Triggered by: "Show my profile", "What's my risk tolerance?", "Update my investment style"</p>
                    <UserProfileDemo />
                </section>
            </div>
            <div className="mt-12 p-4 bg-muted/50 rounded-lg">
                <h3 className="font-semibold mb-2">💡 How it works</h3>
                <p className="text-sm text-muted-foreground">
                    When you chat with the AI and ask crypto-related questions, the AI calls these tools and the corresponding UI components render inline in the chat.
                    This creates a seamless conversational experience where data and actions are embedded directly in the conversation.
                </p>
            </div>
            <div className="mt-4 p-4 bg-green-500/10 rounded-lg border border-green-500/20">
                <h3 className="font-semibold mb-2 text-green-600">✅ All 11 Tool-UI Components Complete</h3>
                <p className="text-sm text-muted-foreground">
                    Components 1-5 (blue) are the original tools. Components 6-11 (orange) are newly added to cover all crypto features in the spec.
                </p>
            </div>
        </div>
    );
}

