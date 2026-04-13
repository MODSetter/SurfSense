"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MessageSquare, Sparkles, Star, Bell, TrendingUp, ArrowRight, X, Plus, User } from "lucide-react";
import {
    MarketOverview,
    WatchlistTable,
    AlertsPanel,
    PortfolioSummary,
    AddTokenModal,
    CreateAlertModal,
    UserProfileSection,
    type AlertConfig,
    type UserProfile,
} from "@/components/crypto";
import {
    MOCK_MARKET_PRICES,
    MOCK_WATCHLIST,
    MOCK_ALERTS,
    MOCK_PORTFOLIO,
} from "@/lib/mock/cryptoMockData";

// Default user profile
const DEFAULT_PROFILE: UserProfile = {
    riskTolerance: "moderate",
    investmentStyle: "swing",
    preferredChains: ["solana", "ethereum"],
    notifications: {
        priceAlerts: true,
        whaleAlerts: true,
        newsAlerts: false,
    },
};

/**
 * Crypto Dashboard Page
 *
 * Full-featured crypto management dashboard with:
 * - Market Overview
 * - Watchlist Management (with Add Token modal)
 * - Alerts Management (with Create Alert modal)
 * - Portfolio Summary
 * - User Profile Settings
 *
 * Also includes a banner promoting the AI Chat for research & analysis.
 */
export default function CryptoDashboardPage() {
    const router = useRouter();
    const params = useParams();
    const searchSpaceId = params.search_space_id;

    // UI State
    const [showAIBanner, setShowAIBanner] = useState(true);
    const [activeTab, setActiveTab] = useState("watchlist");
    const [showAddTokenModal, setShowAddTokenModal] = useState(false);
    const [showCreateAlertModal, setShowCreateAlertModal] = useState(false);
    const [alertPrefilledToken, setAlertPrefilledToken] = useState<{ symbol: string; chain: string } | undefined>();

    // Data State (mock - would be from API in production)
    const [watchlist, setWatchlist] = useState(MOCK_WATCHLIST);
    const [alerts, setAlerts] = useState(MOCK_ALERTS);
    const [userProfile, setUserProfile] = useState<UserProfile>(DEFAULT_PROFILE);

    const handleGoToChat = () => {
        router.push(`/dashboard/${searchSpaceId}/new-chat`);
    };

    const handleTokenClick = (token: any) => {
        router.push(`/dashboard/${searchSpaceId}/new-chat?query=Analyze ${token.symbol}`);
    };

    const handleConfigureAlerts = (token: any) => {
        setAlertPrefilledToken({ symbol: token.symbol, chain: token.chain });
        setShowCreateAlertModal(true);
    };

    const handleAlertClick = (alert: any) => {
        router.push(`/dashboard/${searchSpaceId}/new-chat?query=Tell me about ${alert.tokenSymbol}`);
    };

    const handleRemoveToken = (tokenId: string) => {
        setWatchlist((prev) => prev.filter((t) => t.id !== tokenId));
    };

    const handleAddToken = (token: { symbol: string; name: string; chain: string; contractAddress?: string }) => {
        const newToken = {
            id: `token-${Date.now()}`,
            symbol: token.symbol,
            name: token.name,
            chain: token.chain,
            contractAddress: token.contractAddress,
            price: 0,
            priceChange24h: 0,
            safetyScore: undefined,
            alertCount: 0,
        };
        setWatchlist((prev) => [...prev, newToken]);
    };

    const handleCreateAlert = (alertConfig: AlertConfig) => {
        const newAlert = {
            id: `alert-${Date.now()}`,
            tokenSymbol: alertConfig.tokenSymbol,
            chain: alertConfig.chain,
            type: alertConfig.alertType,
            message: `${alertConfig.alertType.replace("_", " ")} alert for ${alertConfig.tokenSymbol}`,
            severity: "info" as const,
            timestamp: new Date().toISOString(),
            isRead: false,
        };
        setAlerts((prev) => [newAlert, ...prev]);
    };

    const handleSaveProfile = (profile: UserProfile) => {
        setUserProfile(profile);
        // In production, save to backend
    };

    return (
        <div className="flex flex-col h-full overflow-auto">
            {/* AI Chat Promotion Banner */}
            {showAIBanner && (
                <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent border-b px-4 py-3">
                    <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-full bg-primary/10">
                                <Sparkles className="h-5 w-5 text-primary" />
                            </div>
                            <div>
                                <p className="font-medium text-sm">
                                    💡 Try our AI Crypto Advisor for deeper analysis!
                                </p>
                                <p className="text-xs text-muted-foreground">
                                    Ask questions like "Is BULLA safe?" or "Set alert if SOL drops 10%"
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button size="sm" onClick={handleGoToChat} className="gap-1">
                                <MessageSquare className="h-4 w-4" />
                                Open AI Chat
                                <ArrowRight className="h-3 w-3" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setShowAIBanner(false)}>
                                <X className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>
                </div>
            )}

            {/* Main Content */}
            <div className="flex-1 p-4 md:p-6 max-w-7xl mx-auto w-full">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        🚀 Crypto Dashboard
                    </h1>
                    <p className="text-muted-foreground text-sm mt-1">
                        Manage your watchlist, alerts, and track market trends
                    </p>
                </div>

                <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
                    <TabsList>
                        <TabsTrigger value="watchlist" className="gap-2">
                            <Star className="h-4 w-4" />
                            Watchlist
                        </TabsTrigger>
                        <TabsTrigger value="alerts" className="gap-2">
                            <Bell className="h-4 w-4" />
                            Alerts
                        </TabsTrigger>
                        <TabsTrigger value="market" className="gap-2">
                            <TrendingUp className="h-4 w-4" />
                            Market
                        </TabsTrigger>
                        <TabsTrigger value="profile" className="gap-2">
                            <User className="h-4 w-4" />
                            Profile
                        </TabsTrigger>
                    </TabsList>

                    {/* Watchlist Tab */}
                    <TabsContent value="watchlist" className="space-y-4">
                        <div className="flex justify-end">
                            <Button onClick={() => setShowAddTokenModal(true)} className="gap-2">
                                <Plus className="h-4 w-4" />
                                Add Token
                            </Button>
                        </div>
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                            <div className="lg:col-span-2">
                                <WatchlistTable
                                    tokens={watchlist}
                                    onTokenClick={handleTokenClick}
                                    onConfigureAlerts={handleConfigureAlerts}
                                    onRemoveToken={handleRemoveToken}
                                />
                            </div>
                            <div>
                                <PortfolioSummary portfolio={MOCK_PORTFOLIO} />
                            </div>
                        </div>
                    </TabsContent>

                    {/* Alerts Tab */}
                    <TabsContent value="alerts" className="space-y-4">
                        <div className="flex justify-end">
                            <Button onClick={() => { setAlertPrefilledToken(undefined); setShowCreateAlertModal(true); }} className="gap-2">
                                <Plus className="h-4 w-4" />
                                Create Alert
                            </Button>
                        </div>
                        <AlertsPanel
                            alerts={alerts}
                            onAlertClick={handleAlertClick}
                        />
                    </TabsContent>

                    {/* Market Tab */}
                    <TabsContent value="market" className="space-y-4">
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            <MarketOverview tokens={MOCK_MARKET_PRICES} />
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="flex flex-col items-center justify-center py-8 text-center">
                                        <Sparkles className="h-12 w-12 text-primary/50 mb-4" />
                                        <h3 className="font-semibold mb-2">Want deeper market insights?</h3>
                                        <p className="text-sm text-muted-foreground mb-4">
                                            Ask our AI about trending tokens, market sentiment, or specific analysis
                                        </p>
                                        <Button onClick={handleGoToChat} className="gap-2">
                                            <MessageSquare className="h-4 w-4" />
                                            Ask AI Advisor
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    </TabsContent>

                    {/* Profile Tab */}
                    <TabsContent value="profile" className="space-y-4">
                        <div className="max-w-xl">
                            <UserProfileSection
                                profile={userProfile}
                                onSave={handleSaveProfile}
                            />
                        </div>
                    </TabsContent>
                </Tabs>
            </div>

            {/* Modals */}
            <AddTokenModal
                open={showAddTokenModal}
                onOpenChange={setShowAddTokenModal}
                onAddToken={handleAddToken}
            />
            <CreateAlertModal
                open={showCreateAlertModal}
                onOpenChange={setShowCreateAlertModal}
                onCreateAlert={handleCreateAlert}
                prefilledToken={alertPrefilledToken}
            />
        </div>
    );
}
