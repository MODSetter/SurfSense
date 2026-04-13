import { cn } from "~/lib/utils";
import { CheckCircle, Bell, Eye, Settings } from "lucide-react";
import { Button } from "@/routes/ui/button";

export interface ActionConfirmationProps {
    /** Type of action that was confirmed */
    actionType: "watchlist_add" | "watchlist_remove" | "alert_set" | "alert_delete";
    /** Token symbol */
    tokenSymbol: string;
    /** Additional details about the action */
    details?: string[];
    /** Callback when view watchlist is clicked */
    onViewWatchlist?: () => void;
    /** Callback when edit alerts is clicked */
    onEditAlerts?: () => void;
    /** Additional class names */
    className?: string;
}

/**
 * ActionConfirmationWidget - Embedded widget showing action confirmation in chat
 * 
 * Used when AI executes an action like adding to watchlist or setting alerts.
 * Displays confirmation with relevant follow-up actions.
 */
export function ActionConfirmationWidget({
    actionType,
    tokenSymbol,
    details = [],
    onViewWatchlist,
    onEditAlerts,
    className,
}: ActionConfirmationProps) {
    const getActionTitle = () => {
        switch (actionType) {
            case "watchlist_add":
                return `${tokenSymbol} added to your watchlist`;
            case "watchlist_remove":
                return `${tokenSymbol} removed from watchlist`;
            case "alert_set":
                return `Alert configured for ${tokenSymbol}`;
            case "alert_delete":
                return `Alert removed for ${tokenSymbol}`;
            default:
                return "Action completed";
        }
    };

    const getIcon = () => {
        switch (actionType) {
            case "watchlist_add":
            case "watchlist_remove":
                return Eye;
            case "alert_set":
            case "alert_delete":
                return Bell;
            default:
                return CheckCircle;
        }
    };

    const Icon = getIcon();

    return (
        <div className={cn(
            "rounded-lg border bg-card p-4 my-2",
            className
        )}>
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-full bg-green-500/10 flex items-center justify-center">
                    <CheckCircle className="h-4 w-4 text-green-500" />
                </div>
                <span className="font-medium text-sm">Action Confirmed</span>
            </div>

            {/* Action details */}
            <div className="bg-muted/50 rounded-md p-3 mb-3">
                <div className="flex items-center gap-2 mb-2">
                    <Icon className="h-4 w-4 text-primary" />
                    <span className="font-medium text-sm">{getActionTitle()}</span>
                </div>

                {details.length > 0 && (
                    <div className="space-y-1 mt-2">
                        <p className="text-xs text-muted-foreground">Also set up:</p>
                        {details.map((detail, index) => (
                            <div key={index} className="flex items-center gap-2 text-xs">
                                <Bell className="h-3 w-3 text-primary" />
                                <span>{detail}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Action buttons */}
            <div className="flex gap-2">
                {(actionType === "watchlist_add" || actionType === "watchlist_remove") && (
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={onViewWatchlist}
                        className="flex-1"
                    >
                        <Eye className="h-3 w-3 mr-1" />
                        View Watchlist
                    </Button>
                )}
                {(actionType === "watchlist_add" || actionType === "alert_set") && (
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={onEditAlerts}
                        className="flex-1"
                    >
                        <Settings className="h-3 w-3 mr-1" />
                        Edit Alerts
                    </Button>
                )}
            </div>
        </div>
    );
}

