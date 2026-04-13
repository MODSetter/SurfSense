"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Info, Plus, X } from "lucide-react";
import type { FC } from "react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
    Form,
    FormControl,
    FormDescription,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { DateRangeSelector } from "../../components/date-range-selector";
import { getConnectorBenefits } from "../connector-benefits";
import type { ConnectFormProps } from "../index";

// Token configuration schema
const tokenSchema = z.object({
    chain: z.string().min(1, "Chain is required"),
    address: z.string().regex(/^0x[a-fA-F0-9]{40}$/, "Invalid token address (must be 0x followed by 40 hex characters)"),
    name: z.string().optional(),
});

type TokenConfig = z.infer<typeof tokenSchema>;

// Form schema
const dexScreenerFormSchema = z.object({
    name: z.string().min(3, {
        message: "Connector name must be at least 3 characters.",
    }),
    tokens: z.array(tokenSchema).min(1, "At least one token is required").max(50, "Maximum 50 tokens allowed"),
});

type DexScreenerFormValues = z.infer<typeof dexScreenerFormSchema>;

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

export const DexScreenerConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
    const isSubmittingRef = useRef(false);
    const [startDate, setStartDate] = useState<Date | undefined>(undefined);
    const [endDate, setEndDate] = useState<Date | undefined>(undefined);
    const [periodicEnabled, setPeriodicEnabled] = useState(false);
    const [frequencyMinutes, setFrequencyMinutes] = useState("1440");
    const [tokens, setTokens] = useState<TokenConfig[]>([
        { chain: "ethereum", address: "", name: "" },
    ]);

    const form = useForm<DexScreenerFormValues>({
        resolver: zodResolver(dexScreenerFormSchema),
        defaultValues: {
            name: "DexScreener Connector",
            tokens: tokens,
        },
    });

    // Sync tokens state with form
    const updateFormTokens = (newTokens: TokenConfig[]) => {
        setTokens(newTokens);
        form.setValue("tokens", newTokens);
    };

    const addToken = () => {
        if (tokens.length < 50) {
            updateFormTokens([...tokens, { chain: "ethereum", address: "", name: "" }]);
        }
    };

    const removeToken = (index: number) => {
        if (tokens.length > 1) {
            updateFormTokens(tokens.filter((_, i) => i !== index));
        }
    };

    const updateToken = (index: number, field: keyof TokenConfig, value: string) => {
        const newTokens = [...tokens];
        newTokens[index] = { ...newTokens[index], [field]: value };
        updateFormTokens(newTokens);
    };

    const handleSubmit = async (values: DexScreenerFormValues) => {
        // Prevent multiple submissions
        if (isSubmittingRef.current || isSubmitting) {
            return;
        }

        isSubmittingRef.current = true;
        try {
            await onSubmit({
                name: values.name,
                connector_type: EnumConnectorName.DEXSCREENER_CONNECTOR,
                config: {
                    tokens: values.tokens,
                },
                is_indexable: true,
                is_active: true,
                last_indexed_at: null,
                periodic_indexing_enabled: periodicEnabled,
                indexing_frequency_minutes: periodicEnabled ? parseInt(frequencyMinutes, 10) : null,
                next_scheduled_at: null,
                startDate,
                endDate,
                periodicEnabled,
                frequencyMinutes,
            });
        } finally {
            isSubmittingRef.current = false;
        }
    };

    return (
        <div className="space-y-6 pb-6">
            <Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 p-2 sm:p-3 flex items-center [&>svg]:relative [&>svg]:left-0 [&>svg]:top-0 [&>svg+div]:translate-y-0">
                <Info className="h-3 w-3 sm:h-4 sm:w-4 shrink-0 ml-1" />
                <div className="-ml-1">
                    <AlertTitle className="text-xs sm:text-sm">No API Key Required</AlertTitle>
                    <AlertDescription className="text-[10px] sm:text-xs !pl-0">
                        DexScreener API is public and free to use. Simply add the tokens you want to track.{" "}
                        <a
                            href="https://docs.dexscreener.com/api/reference"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium underline underline-offset-4"
                        >
                            View API Documentation
                        </a>
                    </AlertDescription>
                </div>
            </Alert>

            <div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
                <Form {...form}>
                    <form
                        id="dexscreener-connect-form"
                        onSubmit={form.handleSubmit(handleSubmit)}
                        className="space-y-4 sm:space-y-6"
                    >
                        <FormField
                            control={form.control}
                            name="name"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel className="text-xs sm:text-sm">Connector Name</FormLabel>
                                    <FormControl>
                                        <Input
                                            placeholder="My Crypto Tracker"
                                            className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
                                            disabled={isSubmitting}
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormDescription className="text-[10px] sm:text-xs">
                                        A friendly name to identify this connector.
                                    </FormDescription>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        {/* Token List */}
                        <div className="space-y-4 pt-4 border-t border-slate-400/20">
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm sm:text-base font-medium">Tracked Tokens</h3>
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
                                                    disabled={isSubmitting}
                                                    className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                                                >
                                                    <X className="h-3 w-3" />
                                                </Button>
                                            )}
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                            <div className="space-y-2">
                                                <Label htmlFor={`chain-${index}`} className="text-xs sm:text-sm">
                                                    Chain
                                                </Label>
                                                <Select
                                                    value={token.chain}
                                                    onValueChange={(value) => updateToken(index, "chain", value)}
                                                    disabled={isSubmitting}
                                                >
                                                    <SelectTrigger
                                                        id={`chain-${index}`}
                                                        className="h-8 sm:h-10 bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
                                                    >
                                                        <SelectValue placeholder="Select chain" />
                                                    </SelectTrigger>
                                                    <SelectContent className="z-[100]">
                                                        {SUPPORTED_CHAINS.map((chain) => (
                                                            <SelectItem
                                                                key={chain.value}
                                                                value={chain.value}
                                                                className="text-xs sm:text-sm"
                                                            >
                                                                {chain.label}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>

                                            <div className="space-y-2">
                                                <Label htmlFor={`address-${index}`} className="text-xs sm:text-sm">
                                                    Token Address
                                                </Label>
                                                <Input
                                                    id={`address-${index}`}
                                                    placeholder="0x..."
                                                    value={token.address}
                                                    onChange={(e) => updateToken(index, "address", e.target.value)}
                                                    className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40 font-mono"
                                                    disabled={isSubmitting}
                                                />
                                            </div>
                                        </div>

                                        <div className="space-y-2">
                                            <Label htmlFor={`name-${index}`} className="text-xs sm:text-sm">
                                                Token Name (Optional)
                                            </Label>
                                            <Input
                                                id={`name-${index}`}
                                                placeholder="e.g., Wrapped Ether"
                                                value={token.name || ""}
                                                onChange={(e) => updateToken(index, "name", e.target.value)}
                                                className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
                                                disabled={isSubmitting}
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
                                disabled={tokens.length >= 50 || isSubmitting}
                                className="w-full h-8 sm:h-10 text-xs sm:text-sm"
                            >
                                <Plus className="h-3 w-3 sm:h-4 sm:w-4 mr-2" />
                                Add Token {tokens.length >= 50 && "(Maximum reached)"}
                            </Button>
                        </div>

                        {/* Indexing Configuration */}
                        <div className="space-y-4 pt-4 border-t border-slate-400/20">
                            <h3 className="text-sm sm:text-base font-medium">Indexing Configuration</h3>

                            {/* Date Range Selector */}
                            <DateRangeSelector
                                startDate={startDate}
                                endDate={endDate}
                                onStartDateChange={setStartDate}
                                onEndDateChange={setEndDate}
                                allowFutureDates={true}
                            />

                            {/* Periodic Sync Config */}
                            <div className="rounded-xl bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6">
                                <div className="flex items-center justify-between">
                                    <div className="space-y-1">
                                        <h3 className="font-medium text-sm sm:text-base">Enable Periodic Sync</h3>
                                        <p className="text-xs sm:text-sm text-muted-foreground">
                                            Automatically re-index at regular intervals
                                        </p>
                                    </div>
                                    <Switch
                                        checked={periodicEnabled}
                                        onCheckedChange={setPeriodicEnabled}
                                        disabled={isSubmitting}
                                    />
                                </div>

                                {periodicEnabled && (
                                    <div className="mt-4 pt-4 border-t border-slate-400/20 space-y-3">
                                        <div className="space-y-2">
                                            <Label htmlFor="frequency" className="text-xs sm:text-sm">
                                                Sync Frequency
                                            </Label>
                                            <Select
                                                value={frequencyMinutes}
                                                onValueChange={setFrequencyMinutes}
                                                disabled={isSubmitting}
                                            >
                                                <SelectTrigger
                                                    id="frequency"
                                                    className="w-full bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
                                                >
                                                    <SelectValue placeholder="Select frequency" />
                                                </SelectTrigger>
                                                <SelectContent className="z-[100]">
                                                    <SelectItem value="5" className="text-xs sm:text-sm">
                                                        Every 5 minutes
                                                    </SelectItem>
                                                    <SelectItem value="15" className="text-xs sm:text-sm">
                                                        Every 15 minutes
                                                    </SelectItem>
                                                    <SelectItem value="60" className="text-xs sm:text-sm">
                                                        Every hour
                                                    </SelectItem>
                                                    <SelectItem value="360" className="text-xs sm:text-sm">
                                                        Every 6 hours
                                                    </SelectItem>
                                                    <SelectItem value="720" className="text-xs sm:text-sm">
                                                        Every 12 hours
                                                    </SelectItem>
                                                    <SelectItem value="1440" className="text-xs sm:text-sm">
                                                        Daily
                                                    </SelectItem>
                                                    <SelectItem value="10080" className="text-xs sm:text-sm">
                                                        Weekly
                                                    </SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </form>
                </Form>
            </div>

            {/* What you get section */}
            {getConnectorBenefits(EnumConnectorName.DEXSCREENER_CONNECTOR) && (
                <div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 px-3 sm:px-6 py-4 space-y-2">
                    <h4 className="text-xs sm:text-sm font-medium">What you get with DexScreener integration:</h4>
                    <ul className="list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
                        {getConnectorBenefits(EnumConnectorName.DEXSCREENER_CONNECTOR)?.map((benefit) => (
                            <li key={benefit}>{benefit}</li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};
