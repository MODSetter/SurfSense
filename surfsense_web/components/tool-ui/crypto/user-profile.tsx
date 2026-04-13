"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { User, Shield, Target, Clock, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// Schema for user profile tool arguments
export const UserProfileArgsSchema = z.object({
    riskTolerance: z.enum(["conservative", "moderate", "aggressive"]),
    investmentStyle: z.enum(["day_trader", "swing", "long_term"]),
    preferredChains: z.array(z.string()),
    portfolioSizeRange: z.enum(["small", "medium", "large"]).optional(),
    experienceLevel: z.enum(["beginner", "intermediate", "advanced"]).optional(),
    notificationPreferences: z.object({
        priceAlerts: z.boolean(),
        whaleAlerts: z.boolean(),
        newsAlerts: z.boolean(),
    }).optional(),
});

export type UserProfileArgs = z.infer<typeof UserProfileArgsSchema>;

// Schema for user profile result
export const UserProfileResultSchema = z.object({
    success: z.boolean(),
    message: z.string().optional(),
});

export type UserProfileResult = z.infer<typeof UserProfileResultSchema>;

const getRiskColor = (risk: string) => {
    switch (risk) {
        case "conservative": return "text-green-500 bg-green-500/10 border-green-500/20";
        case "moderate": return "text-yellow-500 bg-yellow-500/10 border-yellow-500/20";
        case "aggressive": return "text-red-500 bg-red-500/10 border-red-500/20";
        default: return "";
    }
};

const getStyleIcon = (style: string) => {
    switch (style) {
        case "day_trader": return <Zap className="h-4 w-4" />;
        case "swing": return <Target className="h-4 w-4" />;
        case "long_term": return <Clock className="h-4 w-4" />;
        default: return null;
    }
};

const formatStyle = (style: string) => {
    switch (style) {
        case "day_trader": return "Day Trader";
        case "swing": return "Swing Trader";
        case "long_term": return "Long Term Investor";
        default: return style;
    }
};

/**
 * UserProfileToolUI - Displays user's investment profile inline in chat
 * Used when AI responds to "show my profile" or "what's my risk setting?"
 */
export const UserProfileToolUI = makeAssistantToolUI<UserProfileArgs, UserProfileResult>({
    toolName: "get_user_profile",
    render: ({ args, status }) => {
        const isLoading = status.type === "running";

        return (
            <Card className="my-3 overflow-hidden">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <User className="h-5 w-5 text-indigo-500" />
                        Your Investment Profile
                        {isLoading && <Badge variant="outline" className="animate-pulse">Loading...</Badge>}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Main Profile Settings */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Risk Tolerance */}
                        <div className={cn("rounded-lg p-4 border", getRiskColor(args.riskTolerance))}>
                            <div className="flex items-center gap-2 mb-2">
                                <Shield className="h-4 w-4" />
                                <span className="text-sm font-medium">Risk Tolerance</span>
                            </div>
                            <p className="text-lg font-bold capitalize">{args.riskTolerance}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                                {args.riskTolerance === "conservative" && "Prefer stable, lower-risk investments"}
                                {args.riskTolerance === "moderate" && "Balance between risk and reward"}
                                {args.riskTolerance === "aggressive" && "Willing to take higher risks for higher returns"}
                            </p>
                        </div>

                        {/* Investment Style */}
                        <div className="rounded-lg p-4 border bg-muted/50">
                            <div className="flex items-center gap-2 mb-2">
                                {getStyleIcon(args.investmentStyle)}
                                <span className="text-sm font-medium">Investment Style</span>
                            </div>
                            <p className="text-lg font-bold">{formatStyle(args.investmentStyle)}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                                {args.investmentStyle === "day_trader" && "Quick trades, high frequency"}
                                {args.investmentStyle === "swing" && "Hold for days to weeks"}
                                {args.investmentStyle === "long_term" && "Hold for months to years"}
                            </p>
                        </div>
                    </div>

                    {/* Preferred Chains */}
                    <div>
                        <p className="text-sm font-medium text-muted-foreground mb-2">Preferred Chains</p>
                        <div className="flex flex-wrap gap-2">
                            {args.preferredChains.map((chain) => (
                                <Badge key={chain} variant="secondary" className="capitalize">{chain}</Badge>
                            ))}
                        </div>
                    </div>

                    {/* Notification Preferences */}
                    {args.notificationPreferences && (
                        <div>
                            <p className="text-sm font-medium text-muted-foreground mb-2">Notifications</p>
                            <div className="flex flex-wrap gap-2">
                                {args.notificationPreferences.priceAlerts && <Badge variant="outline">Price Alerts</Badge>}
                                {args.notificationPreferences.whaleAlerts && <Badge variant="outline">Whale Alerts</Badge>}
                                {args.notificationPreferences.newsAlerts && <Badge variant="outline">News Alerts</Badge>}
                            </div>
                        </div>
                    )}

                    {/* Edit Hint */}
                    <p className="text-xs text-muted-foreground text-center pt-2">
                        Say "update my risk tolerance to moderate" to change settings
                    </p>
                </CardContent>
            </Card>
        );
    },
});

