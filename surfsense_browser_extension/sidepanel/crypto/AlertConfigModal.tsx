import { useState } from "react";
import { cn } from "~/lib/utils";
import {
    Bell,
    TrendingUp,
    TrendingDown,
    Droplets,
    Users,
    Wallet,
    X,
    Check
} from "lucide-react";
import { Button } from "@/routes/ui/button";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/routes/ui/dialog";

export type AlertType = "price_above" | "price_below" | "price_change" | "volume" | "whale" | "liquidity" | "holder_concentration";

export interface AlertConfig {
    /** Alert type */
    type: AlertType;
    /** Threshold value */
    threshold: number;
    /** Whether alert is enabled */
    enabled: boolean;
}

export interface AlertConfigModalProps {
    /** Whether modal is open */
    open: boolean;
    /** Callback when modal is closed */
    onOpenChange: (open: boolean) => void;
    /** Token symbol */
    tokenSymbol: string;
    /** Current price for reference */
    currentPrice?: string;
    /** Existing alert configurations */
    existingAlerts?: AlertConfig[];
    /** Callback when alerts are saved */
    onSave: (alerts: AlertConfig[]) => void;
}

const ALERT_TYPES: Array<{
    type: AlertType;
    label: string;
    description: string;
    icon: typeof Bell;
    unit: string;
    defaultThreshold: number;
}> = [
    {
        type: "price_above",
        label: "Price Above",
        description: "Alert when price rises above threshold",
        icon: TrendingUp,
        unit: "$",
        defaultThreshold: 0,
    },
    {
        type: "price_below",
        label: "Price Below",
        description: "Alert when price drops below threshold",
        icon: TrendingDown,
        unit: "$",
        defaultThreshold: 0,
    },
    {
        type: "price_change",
        label: "Price Change",
        description: "Alert on significant price movement",
        icon: TrendingUp,
        unit: "%",
        defaultThreshold: 10,
    },
    {
        type: "volume",
        label: "Volume Spike",
        description: "Alert on unusual trading volume",
        icon: TrendingUp,
        unit: "x",
        defaultThreshold: 3,
    },
    {
        type: "whale",
        label: "Whale Activity",
        description: "Alert on large transactions",
        icon: Wallet,
        unit: "$",
        defaultThreshold: 10000,
    },
    {
        type: "liquidity",
        label: "Liquidity Change",
        description: "Alert on liquidity pool changes",
        icon: Droplets,
        unit: "%",
        defaultThreshold: 20,
    },
    {
        type: "holder_concentration",
        label: "Holder Concentration",
        description: "Alert if top holders exceed threshold",
        icon: Users,
        unit: "%",
        defaultThreshold: 50,
    },
];

/**
 * AlertConfigModal - Configure alerts for a token
 * 
 * Features:
 * - Multiple alert types (price, volume, whale, liquidity, holders)
 * - Threshold configuration per alert type
 * - Enable/disable individual alerts
 * - Save all configurations at once
 */
export function AlertConfigModal({
    open,
    onOpenChange,
    tokenSymbol,
    currentPrice,
    existingAlerts = [],
    onSave,
}: AlertConfigModalProps) {
    // Initialize alerts state from existing or defaults
    const [alerts, setAlerts] = useState<AlertConfig[]>(() => {
        return ALERT_TYPES.map(alertType => {
            const existing = existingAlerts.find(a => a.type === alertType.type);
            return existing || {
                type: alertType.type,
                threshold: alertType.defaultThreshold,
                enabled: false,
            };
        });
    });

    const handleToggleAlert = (type: AlertType) => {
        setAlerts(prev => prev.map(alert => 
            alert.type === type 
                ? { ...alert, enabled: !alert.enabled }
                : alert
        ));
    };

    const handleThresholdChange = (type: AlertType, value: number) => {
        setAlerts(prev => prev.map(alert =>
            alert.type === type
                ? { ...alert, threshold: value }
                : alert
        ));
    };

    const handleSave = () => {
        onSave(alerts.filter(a => a.enabled));
        onOpenChange(false);
    };

    const enabledCount = alerts.filter(a => a.enabled).length;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-md max-h-[80vh] overflow-hidden flex flex-col">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Bell className="h-5 w-5" />
                        Configure Alerts for {tokenSymbol}
                    </DialogTitle>
                    {currentPrice && (
                        <p className="text-sm text-muted-foreground">
                            Current price: {currentPrice}
                        </p>
                    )}
                </DialogHeader>

                {/* Alert types list */}
                <div className="flex-1 overflow-y-auto py-4 space-y-3">
                    {ALERT_TYPES.map((alertType) => {
                        const alert = alerts.find(a => a.type === alertType.type)!;
                        const Icon = alertType.icon;

                        return (
                            <div
                                key={alertType.type}
                                className={cn(
                                    "rounded-lg border p-3 transition-colors",
                                    alert.enabled ? "border-primary bg-primary/5" : "border-border"
                                )}
                            >
                                <div className="flex items-start gap-3">
                                    {/* Toggle button */}
                                    <button
                                        onClick={() => handleToggleAlert(alertType.type)}
                                        className={cn(
                                            "w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors",
                                            alert.enabled
                                                ? "bg-primary border-primary text-primary-foreground"
                                                : "border-muted-foreground"
                                        )}
                                    >
                                        {alert.enabled && <Check className="h-3 w-3" />}
                                    </button>

                                    {/* Alert info */}
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <Icon className="h-4 w-4 text-muted-foreground" />
                                            <span className="font-medium text-sm">{alertType.label}</span>
                                        </div>
                                        <p className="text-xs text-muted-foreground mt-0.5">
                                            {alertType.description}
                                        </p>

                                        {/* Threshold input (only when enabled) */}
                                        {alert.enabled && (
                                            <div className="flex items-center gap-2 mt-2">
                                                <span className="text-xs text-muted-foreground">Threshold:</span>
                                                <div className="flex items-center">
                                                    {alertType.unit === "$" && (
                                                        <span className="text-sm text-muted-foreground">$</span>
                                                    )}
                                                    <input
                                                        type="number"
                                                        value={alert.threshold}
                                                        onChange={(e) => handleThresholdChange(
                                                            alertType.type,
                                                            parseFloat(e.target.value) || 0
                                                        )}
                                                        className="w-24 px-2 py-1 text-sm border rounded bg-background"
                                                        min={0}
                                                        step={alertType.unit === "%" ? 1 : 0.01}
                                                    />
                                                    {alertType.unit !== "$" && (
                                                        <span className="text-sm text-muted-foreground ml-1">
                                                            {alertType.unit}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Footer with save button */}
                <div className="flex items-center justify-between pt-4 border-t">
                    <p className="text-sm text-muted-foreground">
                        {enabledCount} alert{enabledCount !== 1 ? "s" : ""} enabled
                    </p>
                    <div className="flex gap-2">
                        <Button variant="outline" onClick={() => onOpenChange(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleSave}>
                            Save Alerts
                        </Button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
