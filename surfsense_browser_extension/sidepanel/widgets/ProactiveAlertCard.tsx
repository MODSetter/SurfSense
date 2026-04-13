import { cn } from "~/lib/utils";
import { AlertTriangle, TrendingUp, Info, X, Bell, ChevronRight } from "lucide-react";
import { Button } from "@/routes/ui/button";

export interface ProactiveAlertData {
    /** Alert ID */
    id: string;
    /** Alert type */
    type: "price_pump" | "price_dump" | "whale_activity" | "volume_spike" | "safety_warning";
    /** Token symbol */
    tokenSymbol: string;
    /** Alert title */
    title: string;
    /** Current price */
    currentPrice?: string;
    /** User's entry price (if applicable) */
    entryPrice?: string;
    /** User's P&L (if applicable) */
    pnl?: string;
    /** Warning messages */
    warnings?: string[];
    /** When the alert was triggered */
    timestamp: Date;
}

export interface ProactiveAlertCardProps {
    /** Alert data */
    alert: ProactiveAlertData;
    /** AI's recommendation text */
    recommendation?: string;
    /** Callback when view details is clicked */
    onViewDetails?: () => void;
    /** Callback when dismiss is clicked */
    onDismiss?: () => void;
    /** Callback when set alert is clicked */
    onSetAlert?: () => void;
    /** Callback when tell me more is clicked */
    onTellMore?: () => void;
    /** Additional class names */
    className?: string;
}

/**
 * ProactiveAlertCard - AI-initiated alert card embedded in chat
 * 
 * Displays proactive alerts from the AI about price movements,
 * whale activity, or safety concerns. Shows user's position if applicable.
 */
export function ProactiveAlertCard({
    alert,
    recommendation,
    onViewDetails,
    onDismiss,
    onSetAlert,
    onTellMore,
    className,
}: ProactiveAlertCardProps) {
    const getAlertIcon = () => {
        switch (alert.type) {
            case "price_pump":
            case "price_dump":
                return TrendingUp;
            case "whale_activity":
            case "volume_spike":
                return AlertTriangle;
            case "safety_warning":
                return AlertTriangle;
            default:
                return Info;
        }
    };

    const getAlertColor = () => {
        switch (alert.type) {
            case "price_pump":
                return "text-green-500 bg-green-500/10";
            case "price_dump":
            case "safety_warning":
                return "text-red-500 bg-red-500/10";
            case "whale_activity":
            case "volume_spike":
                return "text-yellow-500 bg-yellow-500/10";
            default:
                return "text-primary bg-primary/10";
        }
    };

    const Icon = getAlertIcon();
    const colorClass = getAlertColor();

    return (
        <div className={cn(
            "rounded-lg border bg-card p-4 my-2",
            className
        )}>
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <div className={cn("w-8 h-8 rounded-full flex items-center justify-center", colorClass)}>
                        <Icon className="h-4 w-4" />
                    </div>
                    <div>
                        <span className="font-medium text-sm">🚨 ProactiveAlertCard</span>
                        <p className="text-xs text-muted-foreground">
                            {alert.timestamp.toLocaleTimeString()}
                        </p>
                    </div>
                </div>
                <button
                    onClick={onDismiss}
                    className="p-1 hover:bg-muted rounded text-muted-foreground"
                >
                    <X className="h-4 w-4" />
                </button>
            </div>

            {/* Alert content */}
            <div className="bg-muted/50 rounded-md p-3 mb-3">
                <p className="font-medium text-sm mb-2">{alert.title}</p>
                
                {/* Price info */}
                {(alert.currentPrice || alert.entryPrice || alert.pnl) && (
                    <div className="space-y-1 text-xs">
                        {alert.currentPrice && (
                            <div className="flex justify-between">
                                <span className="text-muted-foreground">📊 Current:</span>
                                <span className="font-medium">{alert.currentPrice}</span>
                            </div>
                        )}
                        {alert.entryPrice && (
                            <div className="flex justify-between">
                                <span className="text-muted-foreground">📈 Your entry:</span>
                                <span>{alert.entryPrice}</span>
                            </div>
                        )}
                        {alert.pnl && (
                            <div className="flex justify-between">
                                <span className="text-muted-foreground">💰 Your P&L:</span>
                                <span className={cn(
                                    "font-medium",
                                    alert.pnl.startsWith("+") ? "text-green-500" : "text-red-500"
                                )}>{alert.pnl}</span>
                            </div>
                        )}
                    </div>
                )}

                {/* Warnings */}
                {alert.warnings && alert.warnings.length > 0 && (
                    <div className="mt-2 pt-2 border-t space-y-1">
                        {alert.warnings.map((warning, index) => (
                            <div key={index} className="flex items-center gap-2 text-xs text-yellow-600">
                                <AlertTriangle className="h-3 w-3" />
                                <span>{warning}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* AI Recommendation */}
            {recommendation && (
                <p className="text-sm text-muted-foreground mb-3 italic">
                    {recommendation}
                </p>
            )}

            {/* Action buttons */}
            <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={onTellMore} className="flex-1">
                    <Info className="h-3 w-3 mr-1" />
                    Tell me more
                </Button>
                <Button size="sm" variant="outline" onClick={onViewDetails}>
                    <ChevronRight className="h-3 w-3" />
                </Button>
                <Button size="sm" variant="outline" onClick={onSetAlert}>
                    <Bell className="h-3 w-3" />
                </Button>
            </div>
        </div>
    );
}

