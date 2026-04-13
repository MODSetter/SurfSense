"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Search, Loader2 } from "lucide-react";

interface AddTokenModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onAddToken: (token: { symbol: string; name: string; chain: string; contractAddress?: string }) => void;
}

const SUPPORTED_CHAINS = [
    { value: "solana", label: "Solana" },
    { value: "ethereum", label: "Ethereum" },
    { value: "base", label: "Base" },
    { value: "arbitrum", label: "Arbitrum" },
    { value: "polygon", label: "Polygon" },
];

export function AddTokenModal({ open, onOpenChange, onAddToken }: AddTokenModalProps) {
    const [symbol, setSymbol] = useState("");
    const [name, setName] = useState("");
    const [chain, setChain] = useState("solana");
    const [contractAddress, setContractAddress] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (!symbol.trim()) {
            setError("Token symbol is required");
            return;
        }

        if (!chain) {
            setError("Please select a chain");
            return;
        }

        setIsLoading(true);

        // Simulate API call delay
        await new Promise((resolve) => setTimeout(resolve, 500));

        onAddToken({
            symbol: symbol.toUpperCase().trim(),
            name: name.trim() || symbol.toUpperCase().trim(),
            chain,
            contractAddress: contractAddress.trim() || undefined,
        });

        // Reset form
        setSymbol("");
        setName("");
        setChain("solana");
        setContractAddress("");
        setIsLoading(false);
        onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Plus className="h-5 w-5" />
                        Add Token to Watchlist
                    </DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit}>
                    <div className="grid gap-4 py-4">
                        <div className="grid gap-2">
                            <Label htmlFor="symbol">Token Symbol *</Label>
                            <Input
                                id="symbol"
                                placeholder="e.g., BULLA, SOL, ETH"
                                value={symbol}
                                onChange={(e) => setSymbol(e.target.value)}
                                className="uppercase"
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="name">Token Name</Label>
                            <Input
                                id="name"
                                placeholder="e.g., Bulla Token"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="chain">Chain *</Label>
                            <Select value={chain} onValueChange={setChain}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select chain" />
                                </SelectTrigger>
                                <SelectContent>
                                    {SUPPORTED_CHAINS.map((c) => (
                                        <SelectItem key={c.value} value={c.value}>
                                            {c.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="contract">Contract Address (optional)</Label>
                            <Input
                                id="contract"
                                placeholder="0x... or token mint address"
                                value={contractAddress}
                                onChange={(e) => setContractAddress(e.target.value)}
                            />
                            <p className="text-xs text-muted-foreground">
                                Provide contract address for accurate token identification
                            </p>
                        </div>
                        {error && <p className="text-sm text-red-500">{error}</p>}
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isLoading}>
                            {isLoading ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Adding...
                                </>
                            ) : (
                                <>
                                    <Plus className="h-4 w-4 mr-2" />
                                    Add to Watchlist
                                </>
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

