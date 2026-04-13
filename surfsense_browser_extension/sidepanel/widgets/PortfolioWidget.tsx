import { PortfolioPanel, type PortfolioData, type PortfolioHolding } from "../portfolio/PortfolioPanel";

export interface PortfolioWidgetProps {
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
}

/**
 * PortfolioWidget - Inline portfolio display in chat
 * Wraps PortfolioPanel for conversational UX
 */
export function PortfolioWidget({
    portfolio,
    onRefresh,
    onAnalyzeToken,
    onSetAlert,
    onViewToken,
    onAddPosition,
}: PortfolioWidgetProps) {
    return (
        <div className="my-3 max-h-[600px] overflow-hidden rounded-lg border">
            <PortfolioPanel
                portfolio={portfolio}
                onRefresh={onRefresh}
                onAnalyzeToken={onAnalyzeToken}
                onSetAlert={onSetAlert}
                onViewToken={onViewToken}
                onAddPosition={onAddPosition}
            />
        </div>
    );
}

