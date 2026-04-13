/**
 * Mock data for Crypto Dashboard - SurfSense Web V2
 * Remove or disable in production
 */

// ============================================
// TYPES
// ============================================

export type ChainType = "solana" | "ethereum" | "base" | "arbitrum" | "polygon" | "bsc";

export interface TokenPrice {
    symbol: string;
    name: string;
    price: number;
    priceChange24h: number;
    priceChange7d: number;
    volume24h: number;
    marketCap: number;
    chain: ChainType;
    icon?: string;
}

export interface WatchlistToken {
    id: string;
    symbol: string;
    name: string;
    chain: ChainType;
    contractAddress: string;
    price: number;
    priceChange24h: number;
    volume24h: number;
    marketCap: number;
    liquidity: number;
    safetyScore: number;
    hasAlerts: boolean;
    alertCount?: number;
    addedAt: Date;
}

export interface Alert {
    id: string;
    tokenSymbol: string;
    tokenName: string;
    chain: ChainType;
    type: "price_above" | "price_below" | "price_change" | "volume" | "whale" | "liquidity" | "safety";
    message: string;
    timestamp: Date;
    isRead: boolean;
    severity: "info" | "warning" | "critical";
}

export interface PortfolioToken {
    id: string;
    symbol: string;
    name: string;
    chain: ChainType;
    amount: number;
    avgBuyPrice: number;
    currentPrice: number;
    value: number;
    pnl: number;
    pnlPercent: number;
    allocation: number;
}

export interface PortfolioSummary {
    totalValue: number;
    totalPnl: number;
    totalPnlPercent: number;
    change24h: number;
    change24hPercent: number;
    tokens: PortfolioToken[];
}

// ============================================
// MARKET OVERVIEW DATA
// ============================================

export const MOCK_MARKET_PRICES: TokenPrice[] = [
    {
        symbol: "BTC",
        name: "Bitcoin",
        price: 97542.18,
        priceChange24h: 2.34,
        priceChange7d: 8.12,
        volume24h: 42_500_000_000,
        marketCap: 1_920_000_000_000,
        chain: "ethereum",
        icon: "₿",
    },
    {
        symbol: "ETH",
        name: "Ethereum",
        price: 3456.78,
        priceChange24h: -1.23,
        priceChange7d: 5.67,
        volume24h: 18_200_000_000,
        marketCap: 415_000_000_000,
        chain: "ethereum",
        icon: "Ξ",
    },
    {
        symbol: "SOL",
        name: "Solana",
        price: 198.45,
        priceChange24h: 5.67,
        priceChange7d: 12.34,
        volume24h: 4_500_000_000,
        marketCap: 92_000_000_000,
        chain: "solana",
        icon: "◎",
    },
];

export const MOCK_TRENDING_TOKENS: TokenPrice[] = [
    {
        symbol: "BULLA",
        name: "Bulla Token",
        price: 0.00001234,
        priceChange24h: 156.7,
        priceChange7d: 342.5,
        volume24h: 1_200_000,
        marketCap: 2_100_000,
        chain: "solana",
    },
    {
        symbol: "BONK",
        name: "Bonk",
        price: 0.00002156,
        priceChange24h: 12.3,
        priceChange7d: 45.6,
        volume24h: 89_000_000,
        marketCap: 1_450_000_000,
        chain: "solana",
    },
    {
        symbol: "WIF",
        name: "dogwifhat",
        price: 2.45,
        priceChange24h: -5.2,
        priceChange7d: 23.4,
        volume24h: 245_000_000,
        marketCap: 2_450_000_000,
        chain: "solana",
    },
    {
        symbol: "PEPE",
        name: "Pepe",
        price: 0.00001089,
        priceChange24h: 8.7,
        priceChange7d: -12.3,
        volume24h: 567_000_000,
        marketCap: 4_580_000_000,
        chain: "ethereum",
    },
];

// ============================================
// WATCHLIST DATA
// ============================================

export const MOCK_WATCHLIST: WatchlistToken[] = [
    {
        id: "1",
        symbol: "BULLA",
        name: "Bulla Token",
        chain: "solana",
        contractAddress: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        price: 0.00001234,
        priceChange24h: 156.7,
        volume24h: 1_200_000,
        marketCap: 2_100_000,
        liquidity: 450_000,
        safetyScore: 72,
        hasAlerts: true,
        alertCount: 2,
        addedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3),
    },
    {
        id: "2",
        symbol: "BONK",
        name: "Bonk",
        chain: "solana",
        contractAddress: "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        price: 0.00002156,
        priceChange24h: 12.3,
        volume24h: 89_000_000,
        marketCap: 1_450_000_000,
        liquidity: 45_000_000,
        safetyScore: 89,
        hasAlerts: true,
        alertCount: 1,
        addedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 7),
    },
    {
        id: "3",
        symbol: "WIF",
        name: "dogwifhat",
        chain: "solana",
        contractAddress: "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        price: 2.45,
        priceChange24h: -5.2,
        volume24h: 245_000_000,
        marketCap: 2_450_000_000,
        liquidity: 125_000_000,
        safetyScore: 94,
        hasAlerts: false,
        addedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 14),
    },
    {
        id: "4",
        symbol: "PEPE",
        name: "Pepe",
        chain: "ethereum",
        contractAddress: "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        price: 0.00001089,
        priceChange24h: 8.7,
        volume24h: 567_000_000,
        marketCap: 4_580_000_000,
        liquidity: 234_000_000,
        safetyScore: 85,
        hasAlerts: false,
        addedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 30),
    },
    {
        id: "5",
        symbol: "DEGEN",
        name: "Degen",
        chain: "base",
        contractAddress: "0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed",
        price: 0.0156,
        priceChange24h: -15.3,
        volume24h: 12_000_000,
        marketCap: 156_000_000,
        liquidity: 8_500_000,
        safetyScore: 78,
        hasAlerts: true,
        alertCount: 3,
        addedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5),
    },
];

// ============================================
// ALERTS DATA
// ============================================

export const MOCK_ALERTS: Alert[] = [
    {
        id: "alert-1",
        tokenSymbol: "BULLA",
        tokenName: "Bulla Token",
        chain: "solana",
        type: "price_above",
        message: "BULLA price increased above $0.00001 (+156%)",
        timestamp: new Date(Date.now() - 1000 * 60 * 5),
        isRead: false,
        severity: "info",
    },
    {
        id: "alert-2",
        tokenSymbol: "BULLA",
        tokenName: "Bulla Token",
        chain: "solana",
        type: "whale",
        message: "Large transaction detected: 500M BULLA ($6,170) transferred",
        timestamp: new Date(Date.now() - 1000 * 60 * 15),
        isRead: false,
        severity: "warning",
    },
    {
        id: "alert-3",
        tokenSymbol: "DEGEN",
        tokenName: "Degen",
        chain: "base",
        type: "price_below",
        message: "DEGEN dropped below $0.02 (-15%)",
        timestamp: new Date(Date.now() - 1000 * 60 * 30),
        isRead: false,
        severity: "critical",
    },
    {
        id: "alert-4",
        tokenSymbol: "BONK",
        tokenName: "Bonk",
        chain: "solana",
        type: "volume",
        message: "BONK volume spike: 3x average in last hour",
        timestamp: new Date(Date.now() - 1000 * 60 * 60),
        isRead: true,
        severity: "info",
    },
    {
        id: "alert-5",
        tokenSymbol: "DEGEN",
        tokenName: "Degen",
        chain: "base",
        type: "liquidity",
        message: "DEGEN liquidity decreased by 12% ($1.2M removed)",
        timestamp: new Date(Date.now() - 1000 * 60 * 120),
        isRead: true,
        severity: "warning",
    },
];

// ============================================
// PORTFOLIO DATA
// ============================================

export const MOCK_PORTFOLIO: PortfolioSummary = {
    totalValue: 15_234.56,
    totalPnl: 3_456.78,
    totalPnlPercent: 29.34,
    change24h: 456.12,
    change24hPercent: 3.08,
    tokens: [
        {
            id: "p1",
            symbol: "SOL",
            name: "Solana",
            chain: "solana",
            amount: 25.5,
            avgBuyPrice: 145.00,
            currentPrice: 198.45,
            value: 5_060.48,
            pnl: 1_362.98,
            pnlPercent: 36.86,
            allocation: 33.2,
        },
        {
            id: "p2",
            symbol: "ETH",
            name: "Ethereum",
            chain: "ethereum",
            amount: 1.2,
            avgBuyPrice: 2_800.00,
            currentPrice: 3_456.78,
            value: 4_148.14,
            pnl: 788.14,
            pnlPercent: 23.46,
            allocation: 27.2,
        },
        {
            id: "p3",
            symbol: "BONK",
            name: "Bonk",
            chain: "solana",
            amount: 150_000_000,
            avgBuyPrice: 0.000015,
            currentPrice: 0.00002156,
            value: 3_234.00,
            pnl: 984.00,
            pnlPercent: 43.73,
            allocation: 21.2,
        },
        {
            id: "p4",
            symbol: "WIF",
            name: "dogwifhat",
            chain: "solana",
            amount: 500,
            avgBuyPrice: 1.80,
            currentPrice: 2.45,
            value: 1_225.00,
            pnl: 325.00,
            pnlPercent: 36.11,
            allocation: 8.0,
        },
        {
            id: "p5",
            symbol: "PEPE",
            name: "Pepe",
            chain: "ethereum",
            amount: 100_000_000,
            avgBuyPrice: 0.000012,
            currentPrice: 0.00001089,
            value: 1_089.00,
            pnl: -111.00,
            pnlPercent: -9.25,
            allocation: 7.2,
        },
        {
            id: "p6",
            symbol: "DEGEN",
            name: "Degen",
            chain: "base",
            amount: 30_000,
            avgBuyPrice: 0.012,
            currentPrice: 0.0156,
            value: 468.00,
            pnl: 108.00,
            pnlPercent: 30.00,
            allocation: 3.1,
        },
    ],
};

// ============================================
// HELPER FUNCTIONS
// ============================================

export function formatPrice(price: number): string {
    if (price >= 1000) {
        return `$${price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    } else if (price >= 1) {
        return `$${price.toFixed(2)}`;
    } else if (price >= 0.0001) {
        return `$${price.toFixed(6)}`;
    } else {
        return `$${price.toFixed(10)}`;
    }
}

export function formatLargeNumber(num: number): string {
    if (num >= 1_000_000_000) {
        return `$${(num / 1_000_000_000).toFixed(2)}B`;
    } else if (num >= 1_000_000) {
        return `$${(num / 1_000_000).toFixed(2)}M`;
    } else if (num >= 1_000) {
        return `$${(num / 1_000).toFixed(2)}K`;
    }
    return `$${num.toFixed(2)}`;
}

export function formatPercent(percent: number): string {
    const sign = percent >= 0 ? "+" : "";
    return `${sign}${percent.toFixed(2)}%`;
}

export function getChainColor(chain: ChainType): string {
    const colors: Record<ChainType, string> = {
        solana: "#9945FF",
        ethereum: "#627EEA",
        base: "#0052FF",
        arbitrum: "#28A0F0",
        polygon: "#8247E5",
        bsc: "#F0B90B",
    };
    return colors[chain] || "#888888";
}

export function getChainName(chain: ChainType): string {
    const names: Record<ChainType, string> = {
        solana: "Solana",
        ethereum: "Ethereum",
        base: "Base",
        arbitrum: "Arbitrum",
        polygon: "Polygon",
        bsc: "BNB Chain",
    };
    return names[chain] || chain;
}

export function getSafetyColor(score: number): string {
    if (score >= 80) return "#22C55E"; // green
    if (score >= 60) return "#EAB308"; // yellow
    if (score >= 40) return "#F97316"; // orange
    return "#EF4444"; // red
}

export function getSafetyLabel(score: number): string {
    if (score >= 80) return "Safe";
    if (score >= 60) return "Medium";
    if (score >= 40) return "Risky";
    return "Danger";
}

