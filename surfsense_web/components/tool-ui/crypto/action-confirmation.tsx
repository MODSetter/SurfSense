"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { CheckCircle, Star, Bell, Trash2, Eye, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// Schema for action confirmation tool arguments
export const ActionConfirmationArgsSchema = z.object({
    actionType: z.enum(["watchlist_add", "watchlist_remove", "alert_set", "alert_delete"]),
    tokenSymbol: z.string(),
    details: z.array(z.string()).optional(),
});

export type ActionConfirmationArgs = z.infer<typeof ActionConfirmationArgsSchema>;

// Schema for action confirmation result
export const ActionConfirmationResultSchema = z.object({
    success: z.boolean(),
    message: z.string().optional(),
});

export type ActionConfirmationResult = z.infer<typeof ActionConfirmationResultSchema>;

const ACTION_CONFIG = {
    watchlist_add: {
        icon: Star,
        title: "Added to Watchlist",
        iconColor: "text-yellow-500",
        bgColor: "bg-yellow-500/10",
    },
    watchlist_remove: {
        icon: Trash2,
        title: "Removed from Watchlist",
        iconColor: "text-red-500",
        bgColor: "bg-red-500/10",
    },
    alert_set: {
        icon: Bell,
        title: "Alert Created",
        iconColor: "text-blue-500",
        bgColor: "bg-blue-500/10",
    },
    alert_delete: {
        icon: Trash2,
        title: "Alert Deleted",
        iconColor: "text-red-500",
        bgColor: "bg-red-500/10",
    },
};

/**
 * ActionConfirmationToolUI - Shows confirmation when AI executes actions
 * Used for watchlist add/remove, alert set/delete confirmations
 */
export const ActionConfirmationToolUI = makeAssistantToolUI<ActionConfirmationArgs, ActionConfirmationResult>({
    toolName: "confirm_action",
    render: ({ args, result, status }) => {
        const isLoading = status.type === "running";
        const config = ACTION_CONFIG[args.actionType];
        const Icon = config.icon;

        return (
            <Card className={cn("my-3 overflow-hidden border-l-4", 
                args.actionType.includes("add") || args.actionType === "alert_set" 
                    ? "border-l-green-500" 
                    : "border-l-red-500"
            )}>
                <CardContent className="py-4">
                    <div className="flex items-start gap-3">
                        {/* Icon */}
                        <div className={cn("p-2 rounded-full", config.bgColor)}>
                            {isLoading ? (
                                <div className="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent" />
                            ) : (
                                <CheckCircle className="h-5 w-5 text-green-500" />
                            )}
                        </div>

                        {/* Content */}
                        <div className="flex-1">
                            <div className="flex items-center gap-2">
                                <Icon className={cn("h-4 w-4", config.iconColor)} />
                                <span className="font-medium">{config.title}</span>
                                <Badge variant="secondary" className="font-mono">
                                    {args.tokenSymbol}
                                </Badge>
                            </div>

                            {/* Details */}
                            {args.details && args.details.length > 0 && (
                                <div className="mt-2 text-sm text-muted-foreground">
                                    <p className="mb-1">Default monitoring enabled:</p>
                                    <ul className="list-disc list-inside space-y-0.5">
                                        {args.details.map((detail, i) => (
                                            <li key={i}>{detail}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Result message */}
                            {result?.message && (
                                <p className="mt-2 text-sm text-muted-foreground">{result.message}</p>
                            )}
                        </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex gap-2 mt-4 ml-11">
                        <Button variant="outline" size="sm">
                            <Eye className="h-3 w-3 mr-1" />
                            View Watchlist
                        </Button>
                        {(args.actionType === "watchlist_add" || args.actionType === "alert_set") && (
                            <Button variant="outline" size="sm">
                                <Settings className="h-3 w-3 mr-1" />
                                Edit Alerts
                            </Button>
                        )}
                    </div>
                </CardContent>
            </Card>
        );
    },
});

