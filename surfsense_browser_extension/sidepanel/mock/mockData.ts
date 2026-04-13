/**
 * Mock data for testing SurfSense Extension UI
 * Remove or disable in production
 */

import type { TokenData } from "../context/PageContextProvider";
import type { WatchlistToken, WatchlistAlert } from "../crypto/WatchlistPanel";
import type { SafetyFactor } from "../crypto/SafetyScoreDisplay";
import type { AlertConfig } from "../crypto/AlertConfigModal";
import type { WhaleTransaction } from "../whale/WhaleActivityFeed";
import type { TokenAnalysisData } from "../analysis/TokenAnalysisPanel";
import type { TradingSuggestion } from "../analysis/TradingSuggestionPanel";
import type { PortfolioData } from "../portfolio/PortfolioPanel";

// ============================================
// MOCK TOKEN DATA (DexScreener)
// ============================================

export const MOCK_TOKEN_DATA: TokenData & {
    priceChange24h: number;
    marketCap: string;
    tokenName: string;
} = {
    chain: "solana",
    pairAddress: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    tokenSymbol: "BULLA",
    tokenName: "Bulla Token",
    price: "$0.00001234",
    priceChange24h: 156.7,
    volume24h: "$1.2M",
    liquidity: "$450K",
    marketCap: "$2.1M",
};

export const MOCK_TOKEN_DATA_BEARISH: TokenData & {
    priceChange24h: number;
    marketCap: string;
    tokenName: string;
} = {
    chain: "ethereum",
    pairAddress: "0x1234567890abcdef1234567890abcdef12345678",
    tokenSymbol: "REKT",
    tokenName: "Rekt Token",
    price: "$0.00000042",
    priceChange24h: -78.5,
    volume24h: "$89K",
    liquidity: "$12K",
    marketCap: "$156K",
};

// ============================================
// MOCK SAFETY ANALYSIS
// ============================================

export const MOCK_SAFETY_SCORE = 72;

export const MOCK_SAFETY_FACTORS: SafetyFactor[] = [
    // Positive factors
    {
        category: "Liquidity",
        status: "positive",
        description: "Liquidity pool is locked for 12 months",
    },
    {
        category: "Contract",
        status: "positive",
        description: "Contract is verified on Solscan",
    },
    {
        category: "Age",
        status: "positive",
        description: "Token has been active for 45 days",
    },
    // Warning factors
    {
        category: "Holders",
        status: "warning",
        description: "Top 10 holders own 35% of supply",
    },
    {
        category: "Volume",
        status: "warning",
        description: "Trading volume decreased 40% in last 24h",
    },
    // Danger factors
    {
        category: "Mint Authority",
        status: "danger",
        description: "Mint authority is NOT revoked - tokens can be minted",
    },
];

export const MOCK_SAFETY_SOURCES = [
    "RugCheck.xyz",
    "GoPlus Security",
    "Solscan",
    "DexScreener",
];

// ============================================
// MOCK WATCHLIST
// ============================================

export const MOCK_WATCHLIST_TOKENS: WatchlistToken[] = [
    {
        id: "1",
        symbol: "BULLA",
        name: "Bulla Token",
        chain: "solana",
        contractAddress: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        price: "$0.00001234",
        priceChange24h: 156.7,
        hasAlerts: true,
        alertCount: 2,
    },
    {
        id: "2",
        symbol: "BONK",
        name: "Bonk",
        chain: "solana",
        contractAddress: "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        price: "$0.00002156",
        priceChange24h: 12.3,
        hasAlerts: true,
        alertCount: 1,
    },
    {
        id: "3",
        symbol: "WIF",
        name: "dogwifhat",
        chain: "solana",
        contractAddress: "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        price: "$2.45",
        priceChange24h: -5.2,
        hasAlerts: false,
    },
    {
        id: "4",
        symbol: "PEPE",
        name: "Pepe",
        chain: "ethereum",
        contractAddress: "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        price: "$0.00001089",
        priceChange24h: 8.7,
        hasAlerts: false,
    },
    {
        id: "5",
        symbol: "DEGEN",
        name: "Degen",
        chain: "base",
        contractAddress: "0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed",
        price: "$0.0156",
        priceChange24h: -15.3,
        hasAlerts: true,
        alertCount: 3,
    },
];

export const MOCK_WATCHLIST_ALERTS: WatchlistAlert[] = [
    {
        id: "alert-1",
        tokenSymbol: "BULLA",
        type: "price",
        message: "BULLA price increased above $0.00001 (+156%)",
        timestamp: new Date(Date.now() - 1000 * 60 * 5), // 5 mins ago
        isRead: false,
    },
    {
        id: "alert-2",
        tokenSymbol: "BULLA",
        type: "whale",
        message: "Large transaction detected: 500M BULLA ($6,170) transferred",
        timestamp: new Date(Date.now() - 1000 * 60 * 15), // 15 mins ago
        isRead: false,
    },
    {
        id: "alert-3",
        tokenSymbol: "DEGEN",
        type: "volume",
        message: "DEGEN volume spike: 5x average in last hour",
        timestamp: new Date(Date.now() - 1000 * 60 * 30), // 30 mins ago
        isRead: true,
    },
    {
        id: "alert-4",
        tokenSymbol: "BONK",
        type: "liquidity",
        message: "BONK liquidity increased by 25% ($1.2M added)",
        timestamp: new Date(Date.now() - 1000 * 60 * 60), // 1 hour ago
        isRead: true,
    },
    {
        id: "alert-5",
        tokenSymbol: "DEGEN",
        type: "price",
        message: "DEGEN dropped below $0.02 (-15%)",
        timestamp: new Date(Date.now() - 1000 * 60 * 120), // 2 hours ago
        isRead: true,
    },
];

// ============================================
// MOCK WHALE TRANSACTIONS
// ============================================

export const MOCK_WHALE_TRANSACTIONS: WhaleTransaction[] = [
    {
        id: "whale-1",
        tokenSymbol: "BULLA",
        tokenName: "Bulla Token",
        chain: "solana",
        type: "buy",
        amountUSD: 100000,
        amountTokens: "8.1B",
        walletAddress: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        txHash: "5Kn8WqXZKqYqKqYqKqYqKqYqKqYqKqYqKqYqKqYqKqYq",
        timestamp: new Date(Date.now() - 1000 * 60 * 2), // 2 mins ago
        isSmartMoney: true,
        isInWatchlist: true,
    },
    {
        id: "whale-2",
        tokenSymbol: "BONK",
        tokenName: "Bonk",
        chain: "solana",
        type: "sell",
        amountUSD: 50000,
        amountTokens: "2.3B",
        walletAddress: "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        txHash: "3Hn7WpXZKpYpKpYpKpYpKpYpKpYpKpYpKpYpKpYpKpYp",
        timestamp: new Date(Date.now() - 1000 * 60 * 5), // 5 mins ago
        isSmartMoney: false,
        isInWatchlist: true,
    },
    {
        id: "whale-3",
        tokenSymbol: "PEPE",
        tokenName: "Pepe",
        chain: "ethereum",
        type: "buy",
        amountUSD: 250000,
        amountTokens: "23B",
        walletAddress: "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        txHash: "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        timestamp: new Date(Date.now() - 1000 * 60 * 10), // 10 mins ago
        isSmartMoney: true,
        isInWatchlist: true,
    },
    {
        id: "whale-4",
        tokenSymbol: "WIF",
        tokenName: "dogwifhat",
        chain: "solana",
        type: "buy",
        amountUSD: 75000,
        amountTokens: "30.6K",
        walletAddress: "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        txHash: "4Jm6VoXYJoXoJoXoJoXoJoXoJoXoJoXoJoXoJoXoJoXo",
        timestamp: new Date(Date.now() - 1000 * 60 * 15), // 15 mins ago
        isSmartMoney: false,
        isInWatchlist: true,
    },
    {
        id: "whale-5",
        tokenSymbol: "DEGEN",
        tokenName: "Degen",
        chain: "base",
        type: "sell",
        amountUSD: 35000,
        amountTokens: "2.2M",
        walletAddress: "0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed",
        txHash: "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        timestamp: new Date(Date.now() - 1000 * 60 * 20), // 20 mins ago
        isSmartMoney: false,
        isInWatchlist: true,
    },
    {
        id: "whale-6",
        tokenSymbol: "SOL",
        tokenName: "Solana",
        chain: "solana",
        type: "buy",
        amountUSD: 500000,
        amountTokens: "5K",
        walletAddress: "So11111111111111111111111111111111111111112",
        txHash: "6Lp7XqYZLqZqLqZqLqZqLqZqLqZqLqZqLqZqLqZqLqZq",
        timestamp: new Date(Date.now() - 1000 * 60 * 30), // 30 mins ago
        isSmartMoney: true,
        isInWatchlist: false,
    },
    {
        id: "whale-7",
        tokenSymbol: "MATIC",
        tokenName: "Polygon",
        chain: "ethereum",
        type: "buy",
        amountUSD: 150000,
        amountTokens: "200K",
        walletAddress: "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
        txHash: "0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321",
        timestamp: new Date(Date.now() - 1000 * 60 * 45), // 45 mins ago
        isSmartMoney: false,
        isInWatchlist: false,
    },
];

// ============================================
// MOCK TOKEN ANALYSIS
// ============================================

export const MOCK_TOKEN_ANALYSIS: TokenAnalysisData = {
    tokenAddress: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    tokenSymbol: "BULLA",
    tokenName: "Bulla Token",
    chain: "solana",
    timestamp: new Date(),

    contract: {
        verified: true,
        renounced: true,
        isProxy: false,
        sourceCode: true,
    },

    holders: {
        count: 1234,
        top10Percent: 35,
        distribution: [
            { address: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU", percent: 8.5 },
            { address: "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", percent: 6.2 },
            { address: "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", percent: 5.8 },
        ],
    },

    liquidity: {
        totalUSD: 50000,
        lpLocked: true,
        lpLockDuration: 90,
        liquidityMcapRatio: 0.15,
    },

    volume: {
        volume24h: 100000,
        trend: "increasing",
        volumeLiquidityRatio: 2.0,
    },

    price: {
        current: 0.0001234,
        ath: 0.0005,
        atl: 0.00001,
        change7d: 15.5,
        change30d: 45.2,
        volatility: 12.5,
    },

    social: {
        twitterMentions: 500,
        telegramActivity: 1200,
        redditDiscussions: 45,
        sentimentScore: 0.75,
        sentiment: "positive",
    },

    aiSummary: "BULLA shows strong holder distribution with verified contract and renounced ownership. Volume increasing 200% in 24h with locked liquidity for 90 days. Social sentiment is highly positive with growing community engagement. Moderate risk profile with good upside potential.",
    recommendation: "buy",
    confidence: 75,
};

// ============================================
// MOCK TRADING SUGGESTION
// ============================================

export const MOCK_TRADING_SUGGESTION: TradingSuggestion = {
    tokenAddress: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    tokenSymbol: "BULLA",
    tokenName: "Bulla Token",
    chain: "solana",
    currentPrice: 0.0001234,
    timestamp: new Date(),

    entry: {
        min: 0.0001100,
        max: 0.0001250,
        reasoning: "Strong support zone at 0.00011 with high volume. Current price offers good risk/reward entry.",
    },

    targets: [
        {
            level: 1,
            price: 0.0001800,
            percentGain: 45.8,
            confidence: 85,
        },
        {
            level: 2,
            price: 0.0002500,
            percentGain: 102.6,
            confidence: 70,
        },
        {
            level: 3,
            price: 0.0003500,
            percentGain: 183.7,
            confidence: 50,
        },
    ],

    stopLoss: {
        price: 0.0000950,
        percentLoss: -23.0,
        reasoning: "Below key support level. Invalidates bullish structure if broken.",
    },

    riskReward: 3.2,
    overallConfidence: 78,

    technicalLevels: {
        support: [0.0001100, 0.0000950, 0.0000800],
        resistance: [0.0001800, 0.0002500, 0.0003500],
    },

    reasoning: [
        "Strong accumulation pattern forming on 4H chart",
        "Volume profile shows increasing buyer interest",
        "RSI showing bullish divergence at support",
        "Whale wallets accumulating over past 48 hours",
        "Social sentiment turning positive with growing community",
    ],

    invalidationConditions: [
        "Break below 0.000095 with high volume",
        "Sudden large holder dumping (>5% supply)",
        "Liquidity removal or unlock event",
        "Negative news or security concerns",
    ],
};

// ============================================
// MOCK PORTFOLIO DATA
// ============================================

export const MOCK_PORTFOLIO: PortfolioData = {
    wallets: [
        {
            address: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            chain: "solana",
            type: "phantom",
        },
        {
            address: "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
            chain: "ethereum",
            type: "metamask",
        },
    ],

    totalValue: 12450.50,
    change24h: 850.25,
    change24hPercent: 7.33,

    holdings: [
        {
            tokenAddress: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            chain: "solana",
            symbol: "BULLA",
            name: "Bulla Token",
            amount: "8,100,000",
            currentPrice: 0.0001234,
            currentValue: 1000.00,
            change24h: 150.00,
            change24hPercent: 17.65,
            entryPrice: 0.0001000,
            pnl: 189.54,
            pnlPercent: 23.4,
        },
        {
            tokenAddress: "So11111111111111111111111111111111111111112",
            chain: "solana",
            symbol: "SOL",
            name: "Solana",
            amount: "50",
            currentPrice: 100.50,
            currentValue: 5025.00,
            change24h: 250.00,
            change24hPercent: 5.24,
            entryPrice: 95.00,
            pnl: 275.00,
            pnlPercent: 5.79,
        },
        {
            tokenAddress: "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            chain: "solana",
            symbol: "BONK",
            name: "Bonk",
            amount: "2,300,000,000",
            currentPrice: 0.00001500,
            currentValue: 3450.00,
            change24h: -125.00,
            change24hPercent: -3.50,
            entryPrice: 0.00001200,
            pnl: 690.00,
            pnlPercent: 25.0,
        },
        {
            tokenAddress: "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
            chain: "ethereum",
            symbol: "PEPE",
            name: "Pepe",
            amount: "23,000,000,000",
            currentPrice: 0.00000012,
            currentValue: 2760.00,
            change24h: 180.00,
            change24hPercent: 6.98,
            entryPrice: 0.00000010,
            pnl: 460.00,
            pnlPercent: 20.0,
        },
        {
            tokenAddress: "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            chain: "solana",
            symbol: "WIF",
            name: "dogwifhat",
            amount: "100",
            currentPrice: 2.15,
            currentValue: 215.50,
            change24h: -15.50,
            change24hPercent: -6.71,
            entryPrice: 2.50,
            pnl: -35.00,
            pnlPercent: -14.0,
        },
    ],

    analytics: {
        bestPerformer: {
            symbol: "BONK",
            change: 25.0,
        },
        worstPerformer: {
            symbol: "WIF",
            change: -14.0,
        },
        winRate: 80,
        avgHoldTime: 14,
        totalTrades: 25,
    },
};

// ============================================
// MOCK ALERT CONFIGS
// ============================================

export const MOCK_ALERT_CONFIGS: AlertConfig[] = [
    { type: "price_above", threshold: 0.00002, enabled: true },
    { type: "price_below", threshold: 0.000005, enabled: true },
    { type: "price_change", threshold: 20, enabled: false },
    { type: "volume", threshold: 3, enabled: true },
    { type: "whale", threshold: 10000, enabled: false },
    { type: "liquidity", threshold: 30, enabled: false },
    { type: "holder_concentration", threshold: 50, enabled: false },
];

// ============================================
// MOCK SEARCH SPACES
// ============================================

export const MOCK_SEARCH_SPACES = [
    { id: "crypto", name: "Crypto", icon: "🪙" },
    { id: "general", name: "General", icon: "📚" },
    { id: "research", name: "Research", icon: "🔬" },
    { id: "defi", name: "DeFi", icon: "💰" },
    { id: "nft", name: "NFT", icon: "🖼️" },
];

// ============================================
// MOCK CHAT MESSAGES
// ============================================

export const MOCK_CHAT_MESSAGES = [
    {
        id: "msg-1",
        role: "user" as const,
        content: "Is BULLA token safe to invest?",
        timestamp: new Date(Date.now() - 1000 * 60 * 5),
    },
    {
        id: "msg-2",
        role: "assistant" as const,
        content: `Based on my analysis of BULLA token, here's what I found:

**Safety Score: 72/100** ⚠️ Medium Risk

**✅ Positive Signals:**
- Liquidity is locked for 12 months
- Contract is verified
- Active for 45 days

**⚠️ Warnings:**
- Top 10 holders own 35% of supply
- Volume decreased 40% recently

**🚨 Red Flags:**
- Mint authority is NOT revoked

**Recommendation:** Proceed with caution. The unlocked mint authority is a significant risk factor.`,
        timestamp: new Date(Date.now() - 1000 * 60 * 4),
        thinkingSteps: [
            { id: "1", type: "thinking" as const, title: "Understanding your question...", isComplete: true },
            { id: "2", type: "searching" as const, title: "Fetching token data from DexScreener...", isComplete: true },
            { id: "3", type: "analyzing" as const, title: "Running safety analysis...", isComplete: true },
            { id: "4", type: "complete" as const, title: "Analysis complete", isComplete: true },
        ],
    },
];

// ============================================
// FEATURE FLAGS
// ============================================

export const MOCK_MODE = {
    /** Enable mock data for development/testing */
    enabled: true,
    /** Simulate DexScreener page context */
    simulateDexScreener: true,
    /** Show mock watchlist data */
    showWatchlist: true,
    /** Show mock alerts */
    showAlerts: true,
};

