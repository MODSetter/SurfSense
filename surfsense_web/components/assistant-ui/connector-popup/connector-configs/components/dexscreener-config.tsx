"use client";

import { Plus, X } from "lucide-react";
import type { FC } from "react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import type { ConnectorConfigProps } from "../index";

// Token configuration interface
interface TokenConfig {
    chain: string;
    address: string;
    name?: string;
}

// Supported chains
const SUPPORTED_CHAINS = [
    { value: "ethereum", label: "Ethereum" },
    { value: "bsc", label: "BSC (Binance Smart Chain)" },
    { value: "polygon", label: "Polygon" },
    { value: "arbitrum", label: "Arbitrum" },
    { value: "optimism", label: "Optimism" },
    { value: "base", label: "Base" },
    { value: "avalanche", label: "Avalanche" },
    { value: "solana", label: "Solana" },
] as const;

export const DexScreenerConfig: FC<ConnectorConfigProps> = ({
    connector,
    onConfigChange,
    onNameChange,
}) => {
    const [tokens, setTokens] = useState<TokenConfig[]>(
        (connector.config?.tokens as TokenConfig[]) || []
    );
    const [name, setName] = useState(connector.name || "");

    const handleTokensChange = (newTokens: TokenConfig[]) => {
        setTokens(newTokens);
        onConfigChange?.({ ...connector.config, tokens: newTokens });
    };

    const handleNameChange = (newName: string) => {
        setName(newName);
        onNameChange?.(newName);
    };

    const addToken = () => {
        if (tokens.length < 50) {
            handleTokensChange([...tokens, { chain: "ethereum", address: "", name: "" }]);
        }
    };

    const removeToken = (index: number) => {
        if (tokens.length > 1) {
            handleTokensChange(tokens.filter((_, i) => i !== index));
        }
    };

    const updateToken = (index: number, field: keyof TokenConfig, value: string) => {
        const newTokens = [...tokens];
        newTokens[index] = { ...newTokens[index], [field]: value };
        handleTokensChange(newTokens);
    };

    return (
        <div className="space-y-6">
            {/* Connector Name */}
            <div className="space-y-2">
                <Label htmlFor="connector-name" className="text-sm font-medium">
                    Connector Name
                </Label>
                <Input
                    id="connector-name"
                    value={name}
                    onChange={(e) => handleNameChange(e.target.value)}
                    placeholder="My Crypto Tracker"
                    className="h-10 px-3 text-sm border-slate-400/20 focus-visible:border-slate-400/40"
                />
                <p className="text-xs text-muted-foreground">
                    A friendly name to identify this connector.
                </p>
            </div>

            {/* Token Configuration */}
            <div className="space-y-4 pt-4 border-t border-slate-400/20">
                <div className="flex items-center justify-between">
                    <h3 className="text-base font-medium">Tracked Tokens</h3>
                    <span className="text-xs text-muted-foreground">
                        {tokens.length} / 50 tokens
                    </span>
                </div>

                <div className="space-y-3">
                    {tokens.map((token, index) => (
                        <div
                            key={index}
                            className="rounded-lg border border-slate-400/20 bg-slate-400/5 dark:bg-white/5 p-3 space-y-3"
                        >
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-medium text-muted-foreground">
                                    Token #{index + 1}
                                </span>
                                {tokens.length > 1 && (
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => removeToken(index)}
                                        className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                                    >
                                        <X className="h-3 w-3" />
                                    </Button>
                                )}
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div className="space-y-2">
                                    <Label htmlFor={`chain-${index}`} className="text-sm">
                                        Chain
                                    </Label>
                                    <Select
                                        value={token.chain}
                                        onValueChange={(value) => updateToken(index, "chain", value)}
                                    >
                                        <SelectTrigger
                                            id={`chain-${index}`}
                                            className="h-10 bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-sm"
                                        >
                                            <SelectValue placeholder="Select chain" />
                                        </SelectTrigger>
                                        <SelectContent className="z-[100]">
                                            {SUPPORTED_CHAINS.map((chain) => (
                                                <SelectItem
                                                    key={chain.value}
                                                    value={chain.value}
                                                    className="text-sm"
                                                >
                                                    {chain.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor={`address-${index}`} className="text-sm">
                                        Token Address
                                    </Label>
                                    <Input
                                        id={`address-${index}`}
                                        placeholder="0x..."
                                        value={token.address}
                                        onChange={(e) => updateToken(index, "address", e.target.value)}
                                        className="h-10 px-3 text-sm border-slate-400/20 focus-visible:border-slate-400/40 font-mono"
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor={`name-${index}`} className="text-sm">
                                    Token Name (Optional)
                                </Label>
                                <Input
                                    id={`name-${index}`}
                                    placeholder="e.g., Wrapped Ether"
                                    value={token.name || ""}
                                    onChange={(e) => updateToken(index, "name", e.target.value)}
                                    className="h-10 px-3 text-sm border-slate-400/20 focus-visible:border-slate-400/40"
                                />
                            </div>
                        </div>
                    ))}
                </div>

                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addToken}
                    disabled={tokens.length >= 50}
                    className="w-full h-10 text-sm"
                >
                    <Plus className="h-4 w-4 mr-2" />
                    Add Token {tokens.length >= 50 && "(Maximum reached)"}
                </Button>
            </div>

            {/* Info */}
            <div className="rounded-lg bg-slate-400/5 dark:bg-white/5 p-4 space-y-2">
                <h4 className="text-sm font-medium">Configuration Tips</h4>
                <ul className="list-disc pl-5 text-xs text-muted-foreground space-y-1">
                    <li>Token addresses must be valid 40-character hex strings (0x...)</li>
                    <li>You can track up to 50 tokens per connector</li>
                    <li>Changes are saved automatically when you update the configuration</li>
                    <li>Token names are optional but help identify tokens in search results</li>
                </ul>
            </div>
        </div>
    );
};
