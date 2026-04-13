import { ChartCapturePanel, type ChartCaptureMetadata } from "../capture/ChartCapturePanel";

export interface ChartCaptureWidgetProps {
    /** Current token metadata */
    metadata?: ChartCaptureMetadata;
    /** Callback when capture is clicked */
    onCapture?: () => void;
    /** Callback when export is clicked */
    onExport?: (format: "twitter" | "telegram" | "instagram" | "clipboard") => void;
}

/**
 * ChartCaptureWidget - Inline chart capture tool in chat
 * Wraps ChartCapturePanel for conversational UX
 */
export function ChartCaptureWidget({
    metadata,
    onCapture,
    onExport,
}: ChartCaptureWidgetProps) {
    return (
        <div className="my-3 max-h-[600px] overflow-hidden rounded-lg border">
            <ChartCapturePanel
                metadata={metadata}
                onCapture={onCapture}
                onExport={onExport}
            />
        </div>
    );
}

