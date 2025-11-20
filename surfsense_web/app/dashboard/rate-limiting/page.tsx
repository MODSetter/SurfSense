"use client";

import {
	ArrowLeft,
	ShieldAlert,
	Unlock,
	RefreshCw,
	AlertTriangle,
	CheckCircle,
	Info,
} from "lucide-react";
import Link from "next/link";
import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { DashboardHeader } from "@/components/DashboardHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
	DialogFooter,
} from "@/components/ui/dialog";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { useUser } from "@/hooks";
import { rateLimitApiService } from "@/lib/apis/rate-limit-api.service";
import type {
	BlockedIP,
	BlockedIPsListResponse,
	RateLimitStatistics,
} from "@/contracts/types/rate-limit.types";

export default function RateLimitingPage() {
	const { user, loading: userLoading, error: userError } = useUser();
	const [blockedIPs, setBlockedIPs] = useState<BlockedIP[]>([]);
	const [statistics, setStatistics] = useState<RateLimitStatistics | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [selectedIPs, setSelectedIPs] = useState<Set<string>>(new Set());
	const [showUnlockDialog, setShowUnlockDialog] = useState(false);
	const [ipToUnlock, setIpToUnlock] = useState<string | null>(null);
	const [isUnlocking, setIsUnlocking] = useState(false);
	const [autoRefresh, setAutoRefresh] = useState(true);

	// Fetch blocked IPs
	const fetchBlockedIPs = useCallback(async () => {
		try {
			const response: BlockedIPsListResponse = await rateLimitApiService.getBlockedIPs();
			setBlockedIPs(response.blocked_ips);
			setStatistics(response.statistics);
		} catch (error) {
			console.error("Failed to fetch blocked IPs:", error);
			toast.error("Failed to load blocked IPs");
		} finally {
			setIsLoading(false);
		}
	}, []);

	// Initial load
	useEffect(() => {
		if (user) {
			fetchBlockedIPs();
		}
	}, [user, fetchBlockedIPs]);

	// Auto-refresh every 30 seconds
	useEffect(() => {
		if (!autoRefresh) return;

		const interval = setInterval(() => {
			fetchBlockedIPs();
		}, 30000);

		return () => clearInterval(interval);
	}, [autoRefresh, fetchBlockedIPs]);

	// Handle manual refresh
	const handleRefresh = () => {
		setIsLoading(true);
		fetchBlockedIPs();
	};

	// Toggle IP selection
	const toggleIPSelection = (ipAddress: string) => {
		const newSelected = new Set(selectedIPs);
		if (newSelected.has(ipAddress)) {
			newSelected.delete(ipAddress);
		} else {
			newSelected.add(ipAddress);
		}
		setSelectedIPs(newSelected);
	};

	// Select/deselect all
	const toggleSelectAll = () => {
		if (selectedIPs.size === blockedIPs.length) {
			setSelectedIPs(new Set());
		} else {
			setSelectedIPs(new Set(blockedIPs.map((ip) => ip.ip_address)));
		}
	};

	// Open unlock dialog for single IP
	const handleUnlockClick = (ipAddress: string) => {
		setIpToUnlock(ipAddress);
		setShowUnlockDialog(true);
	};

	// Unlock single IP
	const handleUnlockSingle = async () => {
		if (!ipToUnlock) return;

		setIsUnlocking(true);
		try {
			await rateLimitApiService.unlockIP(ipToUnlock, {
				reason: "Manually unlocked by administrator",
			});
			toast.success(`IP ${ipToUnlock} has been unlocked`);
			setShowUnlockDialog(false);
			setIpToUnlock(null);
			fetchBlockedIPs();
		} catch (error) {
			console.error("Failed to unlock IP:", error);
			toast.error("Failed to unlock IP address");
		} finally {
			setIsUnlocking(false);
		}
	};

	// Bulk unlock selected IPs
	const handleBulkUnlock = async () => {
		if (selectedIPs.size === 0) return;

		setIsUnlocking(true);
		try {
			const response = await rateLimitApiService.bulkUnlockIPs({
				ip_addresses: Array.from(selectedIPs),
				reason: "Bulk unlock by administrator",
			});

			if (response.success) {
				toast.success(`Unlocked ${response.unlocked_count} IP address(es)`);
			} else {
				toast.warning(
					`Unlocked ${response.unlocked_count} IP(s), ${response.failed.length} failed`
				);
			}

			setSelectedIPs(new Set());
			fetchBlockedIPs();
		} catch (error) {
			console.error("Failed to bulk unlock IPs:", error);
			toast.error("Failed to unlock IP addresses");
		} finally {
			setIsUnlocking(false);
		}
	};

	// Format remaining time
	const formatRemainingTime = (seconds: number): string => {
		if (seconds <= 0) return "Expired";

		const hours = Math.floor(seconds / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		const secs = seconds % 60;

		if (hours > 0) {
			return `${hours}h ${minutes}m`;
		} else if (minutes > 0) {
			return `${minutes}m ${secs}s`;
		} else {
			return `${secs}s`;
		}
	};

	// Format date
	const formatDate = (dateString: string): string => {
		const date = new Date(dateString);
		return date.toLocaleString();
	};

	// Check if user is admin
	const isAdmin = user?.is_superuser || false;

	if (userLoading || isLoading) {
		return (
			<div>
				<DashboardHeader />
				<div className="container mx-auto py-8">
					<div className="flex items-center gap-2 mb-6">
						<Link href="/dashboard">
							<Button variant="ghost" size="sm">
								<ArrowLeft className="h-4 w-4 mr-2" />
								Back
							</Button>
						</Link>
					</div>
					<div className="flex items-center justify-center h-64">
						<RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
					</div>
				</div>
			</div>
		);
	}

	if (userError || !user) {
		return (
			<div>
				<DashboardHeader />
				<div className="container mx-auto py-8">
					<Alert variant="destructive">
						<AlertTriangle className="h-4 w-4" />
						<AlertTitle>Error</AlertTitle>
						<AlertDescription>Failed to load user data. Please try again.</AlertDescription>
					</Alert>
				</div>
			</div>
		);
	}

	return (
		<div>
			<DashboardHeader />
			<div className="container mx-auto py-8">
				{/* Header */}
				<div className="flex items-center gap-2 mb-6">
					<Link href="/dashboard">
						<Button variant="ghost" size="sm">
							<ArrowLeft className="h-4 w-4 mr-2" />
							Back
						</Button>
					</Link>
				</div>

				{/* Page Title */}
				<div className="mb-6">
					<h1 className="text-3xl font-bold flex items-center gap-2">
						<ShieldAlert className="h-8 w-8" />
						Rate Limiting Management
					</h1>
					<p className="text-muted-foreground mt-2">
						View and manage IP addresses that have been temporarily blocked due to failed
						authentication attempts.
					</p>
				</div>

				{/* Statistics Cards */}
				{statistics && (
					<div className="grid gap-4 md:grid-cols-4 mb-6">
						<Card>
							<CardHeader className="pb-2">
								<CardTitle className="text-sm font-medium">Active Blocks</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="text-2xl font-bold">{statistics.active_blocks}</div>
							</CardContent>
						</Card>
						<Card>
							<CardHeader className="pb-2">
								<CardTitle className="text-sm font-medium">Blocks (24h)</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="text-2xl font-bold">{statistics.blocks_24h}</div>
							</CardContent>
						</Card>
						<Card>
							<CardHeader className="pb-2">
								<CardTitle className="text-sm font-medium">Blocks (7d)</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="text-2xl font-bold">{statistics.blocks_7d}</div>
							</CardContent>
						</Card>
						<Card>
							<CardHeader className="pb-2">
								<CardTitle className="text-sm font-medium">Avg. Lockout</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="text-2xl font-bold">
									{Math.floor(statistics.avg_lockout_duration / 60)}m
								</div>
							</CardContent>
						</Card>
					</div>
				)}

				{/* Admin Info Alert */}
				{!isAdmin && (
					<Alert className="mb-6">
						<Info className="h-4 w-4" />
						<AlertTitle>View Only</AlertTitle>
						<AlertDescription>
							You can view blocked IP addresses, but only administrators can unlock them. Contact
							an administrator if you need to unblock an IP address.
						</AlertDescription>
					</Alert>
				)}

				{/* Main Content */}
				<Card>
					<CardHeader>
						<div className="flex items-center justify-between">
							<div>
								<CardTitle>Blocked IP Addresses</CardTitle>
								<CardDescription>
									{blockedIPs.length === 0
										? "No IP addresses are currently blocked"
										: `${blockedIPs.length} IP address(es) currently blocked`}
								</CardDescription>
							</div>
							<div className="flex items-center gap-2">
								{isAdmin && selectedIPs.size > 0 && (
									<Button
										variant="outline"
										onClick={handleBulkUnlock}
										disabled={isUnlocking}
									>
										<Unlock className="h-4 w-4 mr-2" />
										Unlock Selected ({selectedIPs.size})
									</Button>
								)}
								<Button variant="outline" size="sm" onClick={handleRefresh}>
									<RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
								</Button>
							</div>
						</div>
					</CardHeader>
					<CardContent>
						{blockedIPs.length === 0 ? (
							<div className="text-center py-12">
								<CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-4" />
								<h3 className="text-lg font-semibold mb-2">No Blocked IPs</h3>
								<p className="text-muted-foreground">
									All IP addresses are currently allowed to access the system.
								</p>
							</div>
						) : (
							<Table>
								<TableHeader>
									<TableRow>
										{isAdmin && (
											<TableHead className="w-12">
												<Checkbox
													checked={selectedIPs.size === blockedIPs.length}
													onCheckedChange={toggleSelectAll}
												/>
											</TableHead>
										)}
										<TableHead>IP Address</TableHead>
										<TableHead>User</TableHead>
										<TableHead>Blocked At</TableHead>
										<TableHead>Time Remaining</TableHead>
										<TableHead>Failed Attempts</TableHead>
										<TableHead>Reason</TableHead>
										{isAdmin && <TableHead className="text-right">Actions</TableHead>}
									</TableRow>
								</TableHeader>
								<TableBody>
									{blockedIPs.map((block) => (
										<TableRow key={block.ip_address}>
											{isAdmin && (
												<TableCell>
													<Checkbox
														checked={selectedIPs.has(block.ip_address)}
														onCheckedChange={() => toggleIPSelection(block.ip_address)}
													/>
												</TableCell>
											)}
											<TableCell className="font-mono">{block.ip_address}</TableCell>
											<TableCell>{block.username || "Unknown"}</TableCell>
											<TableCell>{formatDate(block.blocked_at)}</TableCell>
											<TableCell>
												<Badge variant="secondary">
													{formatRemainingTime(block.remaining_seconds)}
												</Badge>
											</TableCell>
											<TableCell>
												<Badge variant="destructive">{block.failed_attempts}</Badge>
											</TableCell>
											<TableCell className="text-sm text-muted-foreground">
												{block.reason === "exceeded_max_attempts"
													? "Max attempts exceeded"
													: block.reason}
											</TableCell>
											{isAdmin && (
												<TableCell className="text-right">
													<Button
														variant="outline"
														size="sm"
														onClick={() => handleUnlockClick(block.ip_address)}
													>
														<Unlock className="h-4 w-4 mr-2" />
														Unlock
													</Button>
												</TableCell>
											)}
										</TableRow>
									))}
								</TableBody>
							</Table>
						)}
					</CardContent>
				</Card>

				{/* Unlock Confirmation Dialog */}
				<Dialog open={showUnlockDialog} onOpenChange={setShowUnlockDialog}>
					<DialogContent>
						<DialogHeader>
							<DialogTitle>Unlock IP Address</DialogTitle>
							<DialogDescription>
								Are you sure you want to unlock <strong>{ipToUnlock}</strong>? This will
								immediately allow login attempts from this address.
							</DialogDescription>
						</DialogHeader>
						<DialogFooter>
							<Button
								variant="outline"
								onClick={() => setShowUnlockDialog(false)}
								disabled={isUnlocking}
							>
								Cancel
							</Button>
							<Button onClick={handleUnlockSingle} disabled={isUnlocking}>
								{isUnlocking ? (
									<>
										<RefreshCw className="h-4 w-4 mr-2 animate-spin" />
										Unlocking...
									</>
								) : (
									<>
										<Unlock className="h-4 w-4 mr-2" />
										Unlock
									</>
								)}
							</Button>
						</DialogFooter>
					</DialogContent>
				</Dialog>
			</div>
		</div>
	);
}
