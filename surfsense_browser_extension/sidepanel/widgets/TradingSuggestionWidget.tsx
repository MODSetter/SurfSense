import { TradingSuggestionPanel, type TradingSuggestion } from "../analysis/TradingSuggestionPanel";

export interface TradingSuggestionWidgetProps {
    /** Trading suggestion data */
    suggestion: TradingSuggestion;
    /** Callback when "Set Alerts" is clicked */
    onSetAlerts?: () => void;
    /** Callback when "View Chart" is clicked */
    onViewChart?: () => void;
}

/**
 * TradingSuggestionWidget - Inline trading suggestion display in chat
 * Wraps TradingSuggestionPanel for conversational UX
 */
export function TradingSuggestionWidget({
    suggestion,
    onSetAlerts,
    onViewChart,
}: TradingSuggestionWidgetProps) {
    return (
        <div className="my-3 max-h-[600px] overflow-hidden rounded-lg border">
            <TradingSuggestionPanel
                suggestion={suggestion}
                onSetAlerts={onSetAlerts}
                onViewChart={onViewChart}
            />
        </div>
    );
}

