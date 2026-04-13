"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { User, Shield, Target, Bell, Save, Loader2 } from "lucide-react";

export interface UserProfile {
    riskTolerance: "conservative" | "moderate" | "aggressive";
    investmentStyle: "day_trader" | "swing" | "long_term";
    preferredChains: string[];
    notifications: {
        priceAlerts: boolean;
        whaleAlerts: boolean;
        newsAlerts: boolean;
    };
}

interface UserProfileSectionProps {
    profile: UserProfile;
    onSave: (profile: UserProfile) => void;
}

const CHAINS = ["solana", "ethereum", "base", "arbitrum", "polygon"];

export function UserProfileSection({ profile: initialProfile, onSave }: UserProfileSectionProps) {
    const [profile, setProfile] = useState<UserProfile>(initialProfile);
    const [isSaving, setIsSaving] = useState(false);
    const [hasChanges, setHasChanges] = useState(false);

    const updateProfile = (updates: Partial<UserProfile>) => {
        setProfile((prev) => ({ ...prev, ...updates }));
        setHasChanges(true);
    };

    const toggleChain = (chain: string) => {
        const newChains = profile.preferredChains.includes(chain)
            ? profile.preferredChains.filter((c) => c !== chain)
            : [...profile.preferredChains, chain];
        updateProfile({ preferredChains: newChains });
    };

    const handleSave = async () => {
        setIsSaving(true);
        await new Promise((resolve) => setTimeout(resolve, 500));
        onSave(profile);
        setIsSaving(false);
        setHasChanges(false);
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <User className="h-5 w-5" />
                    Investment Profile
                </CardTitle>
                <CardDescription>
                    Configure your risk preferences and notification settings
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                {/* Risk Tolerance */}
                <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                        <Shield className="h-4 w-4" />
                        Risk Tolerance
                    </Label>
                    <Select
                        value={profile.riskTolerance}
                        onValueChange={(v) => updateProfile({ riskTolerance: v as UserProfile["riskTolerance"] })}
                    >
                        <SelectTrigger>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="conservative">Conservative - Lower risk, stable returns</SelectItem>
                            <SelectItem value="moderate">Moderate - Balanced risk/reward</SelectItem>
                            <SelectItem value="aggressive">Aggressive - Higher risk, higher potential</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* Investment Style */}
                <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                        <Target className="h-4 w-4" />
                        Investment Style
                    </Label>
                    <Select
                        value={profile.investmentStyle}
                        onValueChange={(v) => updateProfile({ investmentStyle: v as UserProfile["investmentStyle"] })}
                    >
                        <SelectTrigger>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="day_trader">Day Trader - Quick trades, high frequency</SelectItem>
                            <SelectItem value="swing">Swing Trader - Hold for days to weeks</SelectItem>
                            <SelectItem value="long_term">Long Term - Hold for months to years</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* Preferred Chains */}
                <div className="space-y-2">
                    <Label>Preferred Chains</Label>
                    <div className="flex flex-wrap gap-2">
                        {CHAINS.map((chain) => (
                            <Badge
                                key={chain}
                                variant={profile.preferredChains.includes(chain) ? "default" : "outline"}
                                className="cursor-pointer capitalize"
                                onClick={() => toggleChain(chain)}
                            >
                                {chain}
                            </Badge>
                        ))}
                    </div>
                </div>

                {/* Notifications */}
                <div className="space-y-4">
                    <Label className="flex items-center gap-2">
                        <Bell className="h-4 w-4" />
                        Notifications
                    </Label>
                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <span className="text-sm">Price Alerts</span>
                            <Switch
                                checked={profile.notifications.priceAlerts}
                                onCheckedChange={(v) => updateProfile({ notifications: { ...profile.notifications, priceAlerts: v } })}
                            />
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-sm">Whale Activity Alerts</span>
                            <Switch
                                checked={profile.notifications.whaleAlerts}
                                onCheckedChange={(v) => updateProfile({ notifications: { ...profile.notifications, whaleAlerts: v } })}
                            />
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-sm">News & Updates</span>
                            <Switch
                                checked={profile.notifications.newsAlerts}
                                onCheckedChange={(v) => updateProfile({ notifications: { ...profile.notifications, newsAlerts: v } })}
                            />
                        </div>
                    </div>
                </div>

                {/* Save Button */}
                <Button onClick={handleSave} disabled={!hasChanges || isSaving} className="w-full">
                    {isSaving ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Saving...</> : <><Save className="h-4 w-4 mr-2" />Save Profile</>}
                </Button>
            </CardContent>
        </Card>
    );
}

