"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Bell, Loader2 } from "lucide-react";

interface CreateAlertModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onCreateAlert: (alert: AlertConfig) => void;
    prefilledToken?: { symbol: string; chain: string };
}

export interface AlertConfig {
    tokenSymbol: string;
    chain: string;
    alertType: string;
    threshold?: number;
    enabled: boolean;
}

const ALERT_TYPES = [
    { value: "price_above", label: "Price Above", hasThreshold: true, unit: "$" },
    { value: "price_below", label: "Price Below", hasThreshold: true, unit: "$" },
    { value: "price_change", label: "Price Change %", hasThreshold: true, unit: "%" },
    { value: "volume_spike", label: "Volume Spike", hasThreshold: true, unit: "x" },
    { value: "whale_buy", label: "Whale Buy", hasThreshold: false },
    { value: "whale_sell", label: "Whale Sell", hasThreshold: false },
];

const SUPPORTED_CHAINS = [
    { value: "solana", label: "Solana" },
    { value: "ethereum", label: "Ethereum" },
    { value: "base", label: "Base" },
];

export function CreateAlertModal({ open, onOpenChange, onCreateAlert, prefilledToken }: CreateAlertModalProps) {
    const [tokenSymbol, setTokenSymbol] = useState(prefilledToken?.symbol || "");
    const [chain, setChain] = useState(prefilledToken?.chain || "solana");
    const [alertType, setAlertType] = useState("price_above");
    const [threshold, setThreshold] = useState("");
    const [enabled, setEnabled] = useState(true);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");

    const selectedAlertType = ALERT_TYPES.find((t) => t.value === alertType);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (!tokenSymbol.trim()) {
            setError("Token symbol is required");
            return;
        }

        if (selectedAlertType?.hasThreshold && !threshold) {
            setError("Threshold value is required for this alert type");
            return;
        }

        setIsLoading(true);
        await new Promise((resolve) => setTimeout(resolve, 500));

        onCreateAlert({
            tokenSymbol: tokenSymbol.toUpperCase().trim(),
            chain,
            alertType,
            threshold: selectedAlertType?.hasThreshold ? parseFloat(threshold) : undefined,
            enabled,
        });

        // Reset form
        setTokenSymbol("");
        setAlertType("price_above");
        setThreshold("");
        setEnabled(true);
        setIsLoading(false);
        onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Bell className="h-5 w-5" />
                        Create Alert
                    </DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit}>
                    <div className="grid gap-4 py-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="grid gap-2">
                                <Label htmlFor="token">Token Symbol *</Label>
                                <Input
                                    id="token"
                                    placeholder="e.g., SOL"
                                    value={tokenSymbol}
                                    onChange={(e) => setTokenSymbol(e.target.value)}
                                    className="uppercase"
                                />
                            </div>
                            <div className="grid gap-2">
                                <Label htmlFor="chain">Chain</Label>
                                <Select value={chain} onValueChange={setChain}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {SUPPORTED_CHAINS.map((c) => (
                                            <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="alertType">Alert Type *</Label>
                            <Select value={alertType} onValueChange={setAlertType}>
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {ALERT_TYPES.map((t) => (
                                        <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        {selectedAlertType?.hasThreshold && (
                            <div className="grid gap-2">
                                <Label htmlFor="threshold">Threshold ({selectedAlertType.unit}) *</Label>
                                <Input
                                    id="threshold"
                                    type="number"
                                    step="any"
                                    placeholder={`Enter value in ${selectedAlertType.unit}`}
                                    value={threshold}
                                    onChange={(e) => setThreshold(e.target.value)}
                                />
                            </div>
                        )}
                        <div className="flex items-center justify-between">
                            <Label htmlFor="enabled">Enable Alert</Label>
                            <Switch id="enabled" checked={enabled} onCheckedChange={setEnabled} />
                        </div>
                        {error && <p className="text-sm text-red-500">{error}</p>}
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                        <Button type="submit" disabled={isLoading}>
                            {isLoading ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Creating...</> : <><Bell className="h-4 w-4 mr-2" />Create Alert</>}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

