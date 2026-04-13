"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
    Star,
    Bell,
    ExternalLink,
    MoreHorizontal,
    ArrowUpDown,
    Trash2,
    Settings,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { ChainIcon } from "./ChainIcon";
import { SafetyBadge } from "./SafetyBadge";
import type { WatchlistToken } from "@/lib/mock/cryptoMockData";
import { formatPrice, formatPercent, formatLargeNumber } from "@/lib/mock/cryptoMockData";

interface WatchlistTableProps {
    tokens: WatchlistToken[];
    onTokenClick?: (token: WatchlistToken) => void;
    onRemoveToken?: (tokenId: string) => void;
    onConfigureAlerts?: (token: WatchlistToken) => void;
    className?: string;
}

type SortField = "symbol" | "price" | "priceChange24h" | "volume24h" | "marketCap" | "safetyScore";
type SortDirection = "asc" | "desc";

export function WatchlistTable({
    tokens,
    onTokenClick,
    onRemoveToken,
    onConfigureAlerts,
    className,
}: WatchlistTableProps) {
    const [sortField, setSortField] = useState<SortField>("priceChange24h");
    const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

    const handleSort = (field: SortField) => {
        if (sortField === field) {
            setSortDirection(sortDirection === "asc" ? "desc" : "asc");
        } else {
            setSortField(field);
            setSortDirection("desc");
        }
    };

    const sortedTokens = [...tokens].sort((a, b) => {
        const aVal = a[sortField];
        const bVal = b[sortField];
        if (typeof aVal === "string" && typeof bVal === "string") {
            return sortDirection === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
        }
        return sortDirection === "asc" 
            ? (aVal as number) - (bVal as number) 
            : (bVal as number) - (aVal as number);
    });

    const SortableHeader = ({ field, children }: { field: SortField; children: React.ReactNode }) => (
        <Button
            variant="ghost"
            size="sm"
            className="-ml-3 h-8 data-[state=open]:bg-accent"
            onClick={() => handleSort(field)}
        >
            {children}
            <ArrowUpDown className="ml-2 h-3 w-3" />
        </Button>
    );

    return (
        <Card className={cn("", className)}>
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                    <Star className="h-5 w-5 text-yellow-500" /> Watchlist
                    <Badge variant="secondary" className="ml-2">{tokens.length}</Badge>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="rounded-md border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-[180px]">
                                    <SortableHeader field="symbol">Token</SortableHeader>
                                </TableHead>
                                <TableHead>
                                    <SortableHeader field="price">Price</SortableHeader>
                                </TableHead>
                                <TableHead>
                                    <SortableHeader field="priceChange24h">24h</SortableHeader>
                                </TableHead>
                                <TableHead className="hidden md:table-cell">
                                    <SortableHeader field="volume24h">Volume</SortableHeader>
                                </TableHead>
                                <TableHead className="hidden lg:table-cell">
                                    <SortableHeader field="marketCap">MCap</SortableHeader>
                                </TableHead>
                                <TableHead className="hidden lg:table-cell">
                                    <SortableHeader field="safetyScore">Safety</SortableHeader>
                                </TableHead>
                                <TableHead className="w-[50px]"></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {sortedTokens.map((token) => (
                                <TableRow
                                    key={token.id}
                                    className="cursor-pointer hover:bg-muted/50"
                                    onClick={() => onTokenClick?.(token)}
                                >
                                    <TableCell>
                                        <div className="flex items-center gap-2">
                                            <ChainIcon chain={token.chain} size="sm" />
                                            <div>
                                                <div className="font-medium flex items-center gap-1">
                                                    {token.symbol}
                                                    {token.hasAlerts && (
                                                        <Bell className="h-3 w-3 text-yellow-500" />
                                                    )}
                                                </div>
                                                <div className="text-xs text-muted-foreground">
                                                    {token.name}
                                                </div>
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell className="font-medium">
                                        {formatPrice(token.price)}
                                    </TableCell>
                                    <TableCell>
                                        <span className={cn(
                                            "font-medium",
                                            token.priceChange24h > 0 && "text-green-500",
                                            token.priceChange24h < 0 && "text-red-500"
                                        )}>
                                            {formatPercent(token.priceChange24h)}
                                        </span>
                                    </TableCell>
                                    <TableCell className="hidden md:table-cell">
                                        {formatLargeNumber(token.volume24h)}
                                    </TableCell>
                                    <TableCell className="hidden lg:table-cell">
                                        {formatLargeNumber(token.marketCap)}
                                    </TableCell>
                                    <TableCell className="hidden lg:table-cell">
                                        <SafetyBadge score={token.safetyScore} size="sm" />
                                    </TableCell>
                                    <TableCell>
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                                                <Button variant="ghost" size="icon" className="h-8 w-8">
                                                    <MoreHorizontal className="h-4 w-4" />
                                                </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end">
                                                <DropdownMenuItem onClick={(e) => {
                                                    e.stopPropagation();
                                                    onConfigureAlerts?.(token);
                                                }}>
                                                    <Settings className="mr-2 h-4 w-4" />
                                                    Configure Alerts
                                                </DropdownMenuItem>
                                                <DropdownMenuItem onClick={(e) => {
                                                    e.stopPropagation();
                                                    window.open(`https://dexscreener.com/${token.chain}/${token.contractAddress}`, "_blank");
                                                }}>
                                                    <ExternalLink className="mr-2 h-4 w-4" />
                                                    View on DexScreener
                                                </DropdownMenuItem>
                                                <DropdownMenuItem
                                                    className="text-red-600"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        onRemoveToken?.(token.id);
                                                    }}
                                                >
                                                    <Trash2 className="mr-2 h-4 w-4" />
                                                    Remove
                                                </DropdownMenuItem>
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>
        </Card>
    );
}

