// Conversational UX Widgets for SurfSense Browser Extension
// These widgets are embedded inline in chat messages for a conversation-first experience

export { ActionConfirmationWidget, type ActionConfirmationProps } from "./ActionConfirmationWidget";
export { ProactiveAlertCard, type ProactiveAlertCardProps, type ProactiveAlertData } from "./ProactiveAlertCard";
export { WatchlistWidget, type WatchlistWidgetProps, type WatchlistItem } from "./WatchlistWidget";
export { AlertWidget, type AlertWidgetProps, type AlertConfigData } from "./AlertWidget";
export { TokenAnalysisWidget, type TokenAnalysisWidgetProps, type TokenAnalysisData } from "./TokenAnalysisWidget";

// Epic 2: Smart Monitoring & Alerts
export { WhaleActivityWidget, type WhaleActivityWidgetProps } from "./WhaleActivityWidget";
export { TrendingTokensWidget, type TrendingTokensWidgetProps, type TrendingToken } from "./TrendingTokensWidget";

// Epic 3: Trading Intelligence
export { TradingSuggestionWidget, type TradingSuggestionWidgetProps } from "./TradingSuggestionWidget";
export { PortfolioWidget, type PortfolioWidgetProps } from "./PortfolioWidget";
export { HolderAnalysisWidget, type HolderAnalysisWidgetProps, type HolderAnalysisData, type Holder } from "./HolderAnalysisWidget";

// Epic 4: Content Creation & Productivity
export { ChartCaptureWidget, type ChartCaptureWidgetProps } from "./ChartCaptureWidget";
export { ThreadGeneratorWidget, type ThreadGeneratorWidgetProps } from "./ThreadGeneratorWidget";

// Market Data Widgets
export { MarketOverviewWidget, type MarketOverviewWidgetProps, type MarketOverviewData, type MarketToken } from "./MarketOverviewWidget";
export { LiveTokenPriceWidget, type LiveTokenPriceWidgetProps, type LiveTokenPriceData } from "./LiveTokenPriceWidget";
export { LiveTokenDataWidget, type LiveTokenDataWidgetProps, type LiveTokenDataInfo } from "./LiveTokenDataWidget";

