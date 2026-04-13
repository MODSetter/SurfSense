import { WelcomeScreen } from "./WelcomeScreen";
import { cn } from "~/lib/utils";
import {
    ActionConfirmationWidget,
    ProactiveAlertCard,
    WatchlistWidget,
    AlertWidget,
    TokenAnalysisWidget,
    WhaleActivityWidget,
    TradingSuggestionWidget,
    PortfolioWidget,
    ChartCaptureWidget,
    ThreadGeneratorWidget,
    type ProactiveAlertData,
    type WatchlistItem,
    type AlertConfigData,
    type TokenAnalysisData,
} from "../widgets";
import type { WhaleTransaction } from "../whale/WhaleActivityFeed";
import type { TradingSuggestion } from "../analysis/TradingSuggestionPanel";
import type { PortfolioData } from "../portfolio/PortfolioPanel";
import type { ChartCaptureMetadata } from "../capture/ChartCapturePanel";

// Widget types that can be embedded in messages
export type MessageWidget =
    | { type: "action_confirmation"; actionType: "watchlist_add" | "watchlist_remove" | "alert_set" | "alert_delete"; tokenSymbol: string; details?: string[] }
    | { type: "proactive_alert"; alert: ProactiveAlertData; recommendation?: string }
    | { type: "watchlist"; tokens: WatchlistItem[] }
    | { type: "alert_config"; config: AlertConfigData; isNew?: boolean }
    | { type: "token_analysis"; data: TokenAnalysisData; isInWatchlist?: boolean }
    | { type: "whale_activity"; transactions: WhaleTransaction[] }
    | { type: "trading_suggestion"; suggestion: TradingSuggestion }
    | { type: "portfolio"; portfolio: PortfolioData }
    | { type: "chart_capture"; metadata?: ChartCaptureMetadata }
    | { type: "thread_generator"; tokenAddress?: string; tokenSymbol?: string; chain?: string };

export interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp?: Date;
    isStreaming?: boolean;
    /** Embedded widget to display with this message */
    widget?: MessageWidget;
}

export interface ChatMessagesProps {
    messages: Message[];
    onSuggestionClick?: (text: string) => void;
    userName?: string;
    /** Callbacks for widget interactions */
    onWidgetAction?: (action: string, data?: unknown) => void;
}

/**
 * Chat messages display component with embedded widget support
 * Shows WelcomeScreen when no messages, otherwise displays conversation
 *
 * Supports embedded widgets for conversational UX:
 * - ActionConfirmationWidget: Shows action confirmations
 * - ProactiveAlertCard: AI-initiated alerts
 * - WatchlistWidget: Inline watchlist display
 * - AlertWidget: Alert configuration display
 * - TokenAnalysisWidget: Full token analysis
 * - WhaleActivityWidget: Whale transaction feed (Epic 2)
 * - TradingSuggestionWidget: Entry/exit suggestions (Epic 3)
 * - PortfolioWidget: Portfolio tracker (Epic 3)
 * - ChartCaptureWidget: Chart screenshot tool (Epic 4)
 * - ThreadGeneratorWidget: Twitter thread generator (Epic 4)
 */
export function ChatMessages({
    messages,
    onSuggestionClick,
    userName,
    onWidgetAction,
}: ChatMessagesProps) {
    if (messages.length === 0) {
        return (
            <WelcomeScreen
                userName={userName}
                onSuggestionClick={onSuggestionClick}
            />
        );
    }

    const handleWidgetAction = (action: string, data?: unknown) => {
        onWidgetAction?.(action, data);
    };

    const renderWidget = (widget: MessageWidget) => {
        switch (widget.type) {
            case "action_confirmation":
                return (
                    <ActionConfirmationWidget
                        actionType={widget.actionType}
                        tokenSymbol={widget.tokenSymbol}
                        details={widget.details}
                        onViewWatchlist={() => handleWidgetAction("view_watchlist")}
                        onEditAlerts={() => handleWidgetAction("edit_alerts", widget.tokenSymbol)}
                    />
                );
            case "proactive_alert":
                return (
                    <ProactiveAlertCard
                        alert={widget.alert}
                        recommendation={widget.recommendation}
                        onViewDetails={() => handleWidgetAction("view_alert_details", widget.alert)}
                        onDismiss={() => handleWidgetAction("dismiss_alert", widget.alert.id)}
                        onSetAlert={() => handleWidgetAction("set_alert", widget.alert.tokenSymbol)}
                        onTellMore={() => handleWidgetAction("tell_more", widget.alert)}
                    />
                );
            case "watchlist":
                return (
                    <WatchlistWidget
                        tokens={widget.tokens}
                        onAnalyze={(token) => handleWidgetAction("analyze_token", token)}
                        onRemove={(id) => handleWidgetAction("remove_from_watchlist", id)}
                        onAddToken={() => handleWidgetAction("add_token")}
                        onClearAll={() => handleWidgetAction("clear_watchlist")}
                    />
                );
            case "alert_config":
                return (
                    <AlertWidget
                        config={widget.config}
                        isNew={widget.isNew}
                        onEdit={() => handleWidgetAction("edit_alert", widget.config)}
                        onDelete={() => handleWidgetAction("delete_alert", widget.config)}
                        onAddAnother={() => handleWidgetAction("add_another_alert")}
                        onViewAll={() => handleWidgetAction("view_all_alerts")}
                    />
                );
            case "token_analysis":
                return (
                    <TokenAnalysisWidget
                        data={widget.data}
                        isInWatchlist={widget.isInWatchlist}
                        onAddToWatchlist={() => handleWidgetAction("add_to_watchlist", widget.data)}
                        onSetAlert={() => handleWidgetAction("set_alert", widget.data.symbol)}
                        onAnalyzeFurther={() => handleWidgetAction("analyze_further", widget.data)}
                    />
                );
            case "whale_activity":
                return (
                    <WhaleActivityWidget
                        transactions={widget.transactions}
                        onTrackWallet={(address) => handleWidgetAction("track_wallet", address)}
                        onViewTransaction={(txHash) => handleWidgetAction("view_transaction", txHash)}
                    />
                );
            case "trading_suggestion":
                return (
                    <TradingSuggestionWidget
                        suggestion={widget.suggestion}
                        onSetAlerts={() => handleWidgetAction("set_alerts", widget.suggestion)}
                        onViewChart={() => handleWidgetAction("view_chart", widget.suggestion)}
                    />
                );
            case "portfolio":
                return (
                    <PortfolioWidget
                        portfolio={widget.portfolio}
                        onRefresh={() => handleWidgetAction("refresh_portfolio")}
                        onAnalyzeToken={(holding) => handleWidgetAction("analyze_token", holding)}
                        onSetAlert={(holding) => handleWidgetAction("set_alert", holding)}
                        onViewToken={(holding) => handleWidgetAction("view_token", holding)}
                        onAddPosition={() => handleWidgetAction("add_position")}
                    />
                );
            case "chart_capture":
                return (
                    <ChartCaptureWidget
                        metadata={widget.metadata}
                        onCapture={() => handleWidgetAction("capture_chart")}
                        onExport={(format) => handleWidgetAction("export_chart", format)}
                    />
                );
            case "thread_generator":
                return (
                    <ThreadGeneratorWidget
                        tokenAddress={widget.tokenAddress}
                        tokenSymbol={widget.tokenSymbol}
                        chain={widget.chain}
                        onGenerate={(request) => handleWidgetAction("generate_thread", request)}
                        onExport={(format) => handleWidgetAction("export_thread", format)}
                    />
                );
            default:
                return null;
        }
    };

    return (
        <div className="p-4 space-y-4">
            {messages.map((message) => (
                <div
                    key={message.id}
                    className={cn(
                        "flex flex-col",
                        message.role === "user" ? "items-end" : "items-start"
                    )}
                >
                    {/* Message bubble */}
                    <div
                        className={cn(
                            "max-w-[85%] rounded-lg p-3",
                            message.role === "user"
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted",
                            message.isStreaming && "animate-pulse"
                        )}
                    >
                        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                        {message.timestamp && (
                            <p className="text-xs opacity-60 mt-1">
                                {message.timestamp.toLocaleTimeString([], {
                                    hour: '2-digit',
                                    minute: '2-digit'
                                })}
                            </p>
                        )}
                    </div>

                    {/* Embedded widget (for assistant messages) */}
                    {message.role === "assistant" && message.widget && (
                        <div className="w-full max-w-[95%] mt-2">
                            {renderWidget(message.widget)}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}
