import { cn } from "~/lib/utils";
import { Bell, CheckCircle, Edit, Trash2, Plus } from "lucide-react";
import { Button } from "@/routes/ui/button";

export interface AlertConfigData {
    /** Token symbol */
    tokenSymbol: string;
    /** Alert condition description */
    condition: string;
    /** Current price */
    currentPrice?: string;
    /** Trigger price */
    triggerPrice?: string;
    /** Notification channels */
    channels: {
        browser: boolean;
        inApp: boolean;
        email: boolean;
    };
}

export interface AlertWidgetProps {
    /** Alert configuration data */
    config: AlertConfigData;
    /** Whether this is a new alert or existing */
    isNew?: boolean;
    /** Callback when edit is clicked */
    onEdit?: () => void;
    /** Callback when delete is clicked */
    onDelete?: () => void;
    /** Callback when add another is clicked */
    onAddAnother?: () => void;
    /** Callback when view all alerts is clicked */
    onViewAll?: () => void;
    /** Additional class names */
    className?: string;
}

/**
 * AlertWidget - Embedded alert configuration widget for chat
 * 
 * Shows alert configuration inline in chat after user sets an alert
 * via natural language command.
 */
export function AlertWidget({
    config,
    isNew = true,
    onEdit,
    onDelete,
    onAddAnother,
    onViewAll,
    className,
}: AlertWidgetProps) {
    return (
        <div className={cn(
            "rounded-lg border bg-card p-4 my-2",
            className
        )}>
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                    {isNew ? (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                        <Bell className="h-4 w-4 text-primary" />
                    )}
                </div>
                <span className="font-medium text-sm">
                    {isNew ? "Alert Created" : "AlertWidget"}
                </span>
            </div>

            {/* Alert details */}
            <div className="bg-muted/50 rounded-md p-3 mb-3 space-y-2">
                <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Token:</span>
                    <span className="font-medium">{config.tokenSymbol}</span>
                </div>
                <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Condition:</span>
                    <span className="font-medium">{config.condition}</span>
                </div>
                {config.currentPrice && (
                    <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Current:</span>
                        <span>{config.currentPrice}</span>
                    </div>
                )}
                {config.triggerPrice && (
                    <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Trigger at:</span>
                        <span className="font-medium text-primary">{config.triggerPrice}</span>
                    </div>
                )}

                {/* Notification channels */}
                <div className="pt-2 border-t">
                    <p className="text-xs text-muted-foreground mb-1">Notify via:</p>
                    <div className="flex flex-wrap gap-2">
                        <span className={cn(
                            "text-xs px-2 py-0.5 rounded",
                            config.channels.browser ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground line-through"
                        )}>
                            {config.channels.browser ? "✓" : "✗"} Browser
                        </span>
                        <span className={cn(
                            "text-xs px-2 py-0.5 rounded",
                            config.channels.inApp ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground line-through"
                        )}>
                            {config.channels.inApp ? "✓" : "✗"} In-app
                        </span>
                        <span className={cn(
                            "text-xs px-2 py-0.5 rounded",
                            config.channels.email ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground line-through"
                        )}>
                            {config.channels.email ? "✓" : "✗"} Email
                        </span>
                    </div>
                </div>
            </div>

            {/* Action buttons */}
            <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={onEdit} className="flex-1">
                    <Edit className="h-3 w-3 mr-1" />
                    Edit
                </Button>
                <Button size="sm" variant="outline" onClick={onDelete}>
                    <Trash2 className="h-3 w-3" />
                </Button>
                <Button size="sm" variant="outline" onClick={onAddAnother}>
                    <Plus className="h-3 w-3" />
                </Button>
            </div>

            {/* View all link */}
            {onViewAll && (
                <button
                    onClick={onViewAll}
                    className="w-full mt-2 text-xs text-primary hover:underline"
                >
                    View all alerts →
                </button>
            )}
        </div>
    );
}

