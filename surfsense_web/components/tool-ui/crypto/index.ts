/**
 * Crypto Tool UI Components
 *
 * These components render rich UI for crypto-related AI tools in the chat interface.
 * They follow the conversational UX paradigm where all crypto features are
 * AI-callable tools that render inline in the chat.
 */

// Token Analysis - displays comprehensive token analysis
export {
    TokenAnalysisToolUI,
    TokenAnalysisArgsSchema,
    TokenAnalysisResultSchema,
    type TokenAnalysisArgs,
    type TokenAnalysisResult,
} from "./token-analysis";

// Watchlist Display - shows user's watchlist inline
export {
    WatchlistDisplayToolUI,
    WatchlistDisplayArgsSchema,
    WatchlistDisplayResultSchema,
    type WatchlistDisplayArgs,
    type WatchlistDisplayResult,
} from "./watchlist-display";

// Action Confirmation - confirms executed actions
export {
    ActionConfirmationToolUI,
    ActionConfirmationArgsSchema,
    ActionConfirmationResultSchema,
    type ActionConfirmationArgs,
    type ActionConfirmationResult,
} from "./action-confirmation";

// Alert Configuration - displays/edits alert settings
export {
    AlertConfigurationToolUI,
    AlertConfigurationArgsSchema,
    AlertConfigurationResultSchema,
    type AlertConfigurationArgs,
    type AlertConfigurationResult,
} from "./alert-configuration";

// Proactive Alert - AI-initiated alerts
export {
    ProactiveAlertToolUI,
    ProactiveAlertArgsSchema,
    ProactiveAlertResultSchema,
    type ProactiveAlertArgs,
    type ProactiveAlertResult,
} from "./proactive-alert";

// Trending Tokens - displays hot/trending tokens
export {
    TrendingTokensToolUI,
    TrendingTokensArgsSchema,
    TrendingTokensResultSchema,
    type TrendingTokensArgs,
    type TrendingTokensResult,
} from "./trending-tokens";

// Whale Activity - displays whale transactions
export {
    WhaleActivityToolUI,
    WhaleActivityArgsSchema,
    WhaleActivityResultSchema,
    type WhaleActivityArgs,
    type WhaleActivityResult,
} from "./whale-activity";

// Market Overview - displays market summary
export {
    MarketOverviewToolUI,
    MarketOverviewArgsSchema,
    MarketOverviewResultSchema,
    type MarketOverviewArgs,
    type MarketOverviewResult,
} from "./market-overview-tool";

// Holder Analysis - displays holder distribution
export {
    HolderAnalysisToolUI,
    HolderAnalysisArgsSchema,
    HolderAnalysisResultSchema,
    type HolderAnalysisArgs,
    type HolderAnalysisResult,
} from "./holder-analysis";

// Portfolio Display - displays user's portfolio
export {
    PortfolioDisplayToolUI,
    PortfolioDisplayArgsSchema,
    PortfolioDisplayResultSchema,
    type PortfolioDisplayArgs,
    type PortfolioDisplayResult,
} from "./portfolio-display";

// User Profile - displays user's investment profile
export {
    UserProfileToolUI,
    UserProfileArgsSchema,
    UserProfileResultSchema,
    type UserProfileArgs,
    type UserProfileResult,
} from "./user-profile";

// =========================================================================
// REAL-TIME CRYPTO TOOLS - Hybrid approach (RAG + Real-time)
// =========================================================================
// These components render results from real-time DexScreener API calls.
// Used alongside RAG-based tools for comprehensive crypto analysis.

// Live Token Price - displays real-time price from DexScreener
export {
    LiveTokenPriceToolUI,
    LiveTokenPriceArgsSchema,
    LiveTokenPriceResultSchema,
    type LiveTokenPriceArgs,
    type LiveTokenPriceResult,
} from "./live-token-price";

// Live Token Data - displays comprehensive real-time market data
export {
    LiveTokenDataToolUI,
    LiveTokenDataArgsSchema,
    LiveTokenDataResultSchema,
    type LiveTokenDataArgs,
    type LiveTokenDataResult,
} from "./live-token-data";

// Trading Suggestion - displays AI-powered entry/exit suggestions
export {
    TradingSuggestionToolUI,
    TradingSuggestionArgsSchema,
    TradingSuggestionResultSchema,
    type TradingSuggestionArgs,
    type TradingSuggestionResult,
} from "./trading-suggestion";
