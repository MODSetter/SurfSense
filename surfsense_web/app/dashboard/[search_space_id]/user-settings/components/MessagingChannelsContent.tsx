"use client";

import { MessageCircle, RefreshCw, ShieldAlert } from "lucide-react";
import { useParams } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import type { SearchSpace } from "@/contracts/types/search-space.types";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";
import { buildBackendUrl } from "@/lib/env-config";
import { cn } from "@/lib/utils";

type GatewayConnection = {
	id: number;
	account_id?: number | null;
	route_type?: "account" | "binding";
	platform: string;
	mode?: string;
	state: string;
	search_space_id: number;
	display_name?: string | null;
	external_username?: string | null;
	workspace_name?: string | null;
	workspace_id?: string | null;
	health_status: string;
	suspended_reason?: string | null;
};

type GatewayConfig = {
	enabled: boolean;
	telegram_enabled: boolean;
	whatsapp_intake_mode: "disabled" | "cloud" | "baileys";
	slack_enabled: boolean;
	discord_enabled: boolean;
};

type GatewayConfigState = GatewayConfig | null;

const DISABLED_GATEWAY_CONFIG: GatewayConfig = {
	enabled: false,
	telegram_enabled: false,
	whatsapp_intake_mode: "disabled",
	slack_enabled: false,
	discord_enabled: false,
};

type Pairing = {
	binding_id: number;
	code: string;
	deep_link: string;
	expires_at: string;
};

type PairingPlatform = "telegram" | "whatsapp";
type GatewayPlatform = PairingPlatform | "slack" | "discord";

type BaileysHealth = {
	status: string;
	hasQr: boolean;
	qr?: string | null;
	queueDepth?: number;
	user?: unknown;
};

export function MessagingChannelsContent() {
	const params = useParams<{ search_space_id: string }>();
	const searchSpaceId = Number(params.search_space_id);
	const [gatewayConfig, setGatewayConfig] = useState<GatewayConfigState>(null);
	const [connections, setConnections] = useState<GatewayConnection[]>([]);
	const [searchSpaces, setSearchSpaces] = useState<SearchSpace[]>([]);
	const [pairing, setPairing] = useState<Pairing | null>(null);
	const [pairingPlatform, setPairingPlatform] = useState<PairingPlatform | null>(null);
	const [baileysHealth, setBaileysHealth] = useState<BaileysHealth | null>(null);
	const [refreshingPlatform, setRefreshingPlatform] = useState<GatewayPlatform | null>(null);
	const isGatewayConfigLoading = gatewayConfig === null;
	const telegramGatewayEnabled = gatewayConfig?.telegram_enabled ?? false;
	const whatsappMode = gatewayConfig?.whatsapp_intake_mode ?? "disabled";
	const slackGatewayEnabled = gatewayConfig?.slack_enabled ?? false;
	const discordGatewayEnabled = gatewayConfig?.discord_enabled ?? false;
	const gatewayDisabled = gatewayConfig?.enabled === false;

	const fetchConnections = useCallback(async (platform?: GatewayPlatform) => {
		const res = await authenticatedFetch(
			buildBackendUrl("/api/v1/gateway/connections", platform ? { platform } : undefined)
		);
		if (!res.ok) return [];
		const data = await res.json();
		return Array.isArray(data) ? (data as GatewayConnection[]) : [];
	}, []);

	const fetchGatewayConfig = useCallback(async (): Promise<GatewayConfig> => {
		const res = await authenticatedFetch(buildBackendUrl("/api/v1/gateway/config"));
		if (!res.ok) return DISABLED_GATEWAY_CONFIG;
		const data = (await res.json()) as Partial<GatewayConfig>;
		return {
			...DISABLED_GATEWAY_CONFIG,
			...data,
			enabled: data.enabled ?? true,
		};
	}, []);

	const refresh = useCallback(async () => {
		const [nextConnections, spaces, nextGatewayConfig] = await Promise.all([
			fetchConnections(),
			searchSpacesApiService.getSearchSpaces(),
			fetchGatewayConfig(),
		]);
		setConnections(nextConnections);
		setSearchSpaces(spaces);
		setGatewayConfig(nextGatewayConfig);
	}, [fetchConnections, fetchGatewayConfig]);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const refreshPlatform = useCallback(
		async (platform: GatewayPlatform) => {
			setRefreshingPlatform(platform);
			try {
				const nextConnections = await fetchConnections(platform);
				setConnections((current) => [
					...current.filter((connection) => connection.platform !== platform),
					...nextConnections,
				]);
			} finally {
				setRefreshingPlatform(null);
			}
		},
		[fetchConnections]
	);

	const refreshBaileysHealth = useCallback(async () => {
		if (whatsappMode !== "baileys") return;
		const res = await authenticatedFetch(
			buildBackendUrl("/api/v1/gateway/whatsapp/baileys/health")
		);
		if (!res.ok) return;
		const data = (await res.json()) as BaileysHealth;
		setBaileysHealth(data);
	}, [whatsappMode]);

	useEffect(() => {
		void refreshBaileysHealth();
	}, [refreshBaileysHealth]);

	async function startPairing(platform: PairingPlatform) {
		const res = await authenticatedFetch(buildBackendUrl("/api/v1/gateway/bindings/start"), {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ platform, search_space_id: searchSpaceId }),
		});
		setPairing(await res.json());
		setPairingPlatform(platform);
		await refreshPlatform(platform);
	}

	async function installSlackGateway() {
		const res = await authenticatedFetch(
			buildBackendUrl("/api/v1/gateway/slack/install", { search_space_id: searchSpaceId })
		);
		if (!res.ok) return;
		const data = (await res.json()) as { auth_url?: string };
		if (data.auth_url) {
			window.location.href = data.auth_url;
		}
	}

	async function installDiscordGateway() {
		const res = await authenticatedFetch(
			buildBackendUrl("/api/v1/gateway/discord/install", { search_space_id: searchSpaceId })
		);
		if (!res.ok) return;
		const data = (await res.json()) as { auth_url?: string };
		if (data.auth_url) {
			window.location.href = data.auth_url;
		}
	}

	async function refreshBaileys() {
		await refreshBaileysHealth();
		await refreshPlatform("whatsapp");
	}

	const connectionKey = (connection: GatewayConnection) =>
		connection.route_type === "account" && connection.account_id
			? `account:${connection.account_id}`
			: `binding:${connection.id}`;

	async function revoke(connection: GatewayConnection) {
		const url =
			connection.route_type === "account" && connection.account_id
				? buildBackendUrl(`/api/v1/gateway/accounts/${connection.account_id}`)
				: buildBackendUrl(`/api/v1/gateway/bindings/${connection.id}`);
		await authenticatedFetch(url, {
			method: "DELETE",
		});
		await refreshPlatform(connection.platform as GatewayPlatform);
	}

	async function updateConnectionSearchSpace(
		connection: GatewayConnection,
		nextSearchSpaceId: string
	) {
		const previousConnections = connections;
		const parsedSearchSpaceId = Number(nextSearchSpaceId);
		const targetKey = connectionKey(connection);
		setConnections((current) =>
			current.map((connection) =>
				connectionKey(connection) === targetKey
					? { ...connection, search_space_id: parsedSearchSpaceId }
					: connection
			)
		);
		const url =
			connection.route_type === "account" && connection.account_id
				? buildBackendUrl(`/api/v1/gateway/accounts/${connection.account_id}/search-space`)
				: buildBackendUrl(`/api/v1/gateway/bindings/${connection.id}/search-space`);
		const res = await authenticatedFetch(url, {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ search_space_id: parsedSearchSpaceId }),
		});
		if (!res.ok) {
			setConnections(previousConnections);
			toast.error("Failed to update messaging route");
			return;
		}
		toast.success("Messaging route updated");
		await refreshPlatform(connection.platform as GatewayPlatform);
	}

	async function resume(connection: GatewayConnection) {
		await authenticatedFetch(buildBackendUrl(`/api/v1/gateway/bindings/${connection.id}/resume`), {
			method: "POST",
		});
		await refreshPlatform(connection.platform as GatewayPlatform);
	}

	const isConnectionInActiveMode = (connection: GatewayConnection) => {
		if (connection.platform !== "whatsapp") return true;
		if (whatsappMode === "baileys") return connection.mode === "self_host_byo";
		if (whatsappMode === "cloud") return connection.mode !== "self_host_byo";
		return false;
	};
	const baileysQr = baileysHealth?.qr || null;
	const hasTelegramConnection = connections.some(
		(connection) => connection.platform === "telegram"
	);
	const hasWhatsAppConnection = connections.some(
		(connection) => connection.platform === "whatsapp" && isConnectionInActiveMode(connection)
	);
	const hasEnabledGateway =
		telegramGatewayEnabled ||
		whatsappMode !== "disabled" ||
		slackGatewayEnabled ||
		discordGatewayEnabled;
	const isRefreshing = (platform: GatewayPlatform) => refreshingPlatform === platform;
	const refreshButtonClassName = "gap-2";
	const refreshIconClassName = (platform: GatewayPlatform) =>
		cn("mr-2 h-4 w-4", isRefreshing(platform) && "animate-spin");
	const platformLabel = (platform: string) => {
		switch (platform) {
			case "discord":
				return "Discord";
			case "slack":
				return "Slack";
			case "telegram":
				return "Telegram";
			case "whatsapp":
				return "WhatsApp";
			default:
				return platform;
		}
	};
	const connectionTitle = (connection: GatewayConnection) =>
		connection.platform === "whatsapp" && connection.mode === "self_host_byo"
			? "WhatsApp Bridge"
			: connection.workspace_name ||
				connection.display_name ||
				connection.external_username ||
				`${platformLabel(connection.platform)} connection`;
	const renderConnectionRows = (platform: GatewayConnection["platform"], emptyText: string) => {
		const platformConnections = connections.filter(
			(connection) => connection.platform === platform && isConnectionInActiveMode(connection)
		);

		if (platformConnections.length === 0) {
			return (
				<div className="flex min-h-24 items-center justify-center text-center">
					<p className="text-xs text-muted-foreground">{emptyText}</p>
				</div>
			);
		}

		return (
			<div className="space-y-2">
				<p className="text-xs font-medium text-muted-foreground">Connected accounts</p>
				{platformConnections.map((connection, index) => (
					<div key={connectionKey(connection)} className="space-y-2">
						{index > 0 ? <Separator className="bg-accent" /> : null}
						<div className="space-y-2">
							<div className="min-w-0">
								<p className="truncate text-xs font-medium">{connectionTitle(connection)}</p>
								{connection.suspended_reason ? (
									<p className="mt-1 flex items-center gap-1 text-xs text-destructive">
										<ShieldAlert className="h-3 w-3" />
										{connection.suspended_reason}
									</p>
								) : null}
							</div>
							<div className="flex flex-wrap items-center gap-2">
								<Select
									value={String(connection.search_space_id)}
									onValueChange={(value) => updateConnectionSearchSpace(connection, value)}
									disabled={searchSpaces.length === 0}
								>
									<SelectTrigger className="h-8 min-w-[180px] flex-1 text-xs">
										<SelectValue placeholder="Select search space" />
									</SelectTrigger>
									<SelectContent>
										{searchSpaces.map((space) => (
											<SelectItem key={space.id} value={String(space.id)}>
												{space.name}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
								{connection.state === "suspended" ? (
									<Button
										size="sm"
										variant="outline"
										className="h-8"
										onClick={() => resume(connection)}
									>
										Resume
									</Button>
								) : null}
								<Button
									size="sm"
									variant="destructive"
									className="text-xs sm:text-sm flex-1 sm:flex-initial h-12 sm:h-auto py-3 sm:py-2"
									onClick={() => revoke(connection)}
								>
									Disconnect
								</Button>
							</div>
						</div>
					</div>
				))}
			</div>
		);
	};
	const renderPairingPanel = (platform: PairingPlatform) => {
		if (!pairing || pairingPlatform !== platform) return null;

		return (
			<div className="rounded-lg border border-accent bg-accent/20 p-3">
				<p className="text-xs font-medium">Pairing code</p>
				<p className="mt-2 font-mono text-lg">{pairing.code}</p>
				<a className="mt-2 block text-sm text-primary underline" href={pairing.deep_link}>
					Open {platform === "whatsapp" ? "WhatsApp" : "Telegram"} pairing link
				</a>
				<p className="mt-2 text-xs text-muted-foreground">
					Expires at {new Date(pairing.expires_at).toLocaleString()}. SurfSense stores this
					channel's messages for agent memory and operational debugging.
				</p>
			</div>
		);
	};
	const renderGatewaySkeletons = () => (
		<>
			{[0, 1].map((index) => (
				<Card key={index} className="h-full overflow-hidden border-accent bg-accent/20">
					<CardHeader className="space-y-3 p-4">
						<Skeleton className="h-4 w-24 bg-accent" />
						<Skeleton className="h-3 w-3/4 bg-accent" />
					</CardHeader>
					<CardContent className="space-y-3 p-4 pt-0">
						<Skeleton className="h-8 w-40 bg-accent" />
						<Separator className="bg-accent" />
						<Skeleton className="h-10 w-full bg-accent" />
					</CardContent>
				</Card>
			))}
		</>
	);

	return (
		<div className="grid items-stretch gap-3 sm:grid-cols-2">
			{isGatewayConfigLoading ? renderGatewaySkeletons() : null}

			{!isGatewayConfigLoading && gatewayDisabled ? (
				<Card className="col-span-full border-accent bg-accent/20">
					<CardHeader className="space-y-3 p-4">
						<div className="flex items-center gap-2">
							<MessageCircle className="h-5 w-5 text-primary" />
							<CardTitle className="text-base">Messaging Channels coming soon</CardTitle>
						</div>
						<p className="text-sm text-muted-foreground">
							Soon you'll be able to connect WhatsApp, Telegram, Slack, and Discord to your
							SurfSense agent so you can ask questions, route messages to search spaces, and get
							answers from your knowledge base without leaving your chat app.
						</p>
					</CardHeader>
					<CardContent className="space-y-2 p-4 pt-0 text-sm text-muted-foreground">
						<p>Pair a chat once, then DM the SurfSense agent like a teammate.</p>
						<p>Each channel can be routed to the right search space when integrations launch.</p>
					</CardContent>
				</Card>
			) : null}

			{!isGatewayConfigLoading && !gatewayDisabled && !hasEnabledGateway ? (
				<Card className="col-span-full border-accent bg-accent/20">
					<CardHeader className="space-y-1.5 p-4">
						<CardTitle className="text-sm">No messaging gateways enabled</CardTitle>
					</CardHeader>
				</Card>
			) : null}

			{!gatewayDisabled && telegramGatewayEnabled ? (
				<Card className="order-1 group relative h-full overflow-hidden border-accent bg-accent/20 transition-all duration-200 hover:shadow-md">
					<CardHeader className="space-y-1.5 p-4 pb-2">
						<div className="flex items-center justify-between gap-3">
							<CardTitle className="flex items-center gap-2 text-sm">Telegram</CardTitle>
						</div>
						<p className="text-xs text-muted-foreground">
							Connect Telegram to chat with SurfSense.
						</p>
					</CardHeader>
					<CardContent className="space-y-3 p-4 pt-0">
						<div className="flex flex-wrap gap-2">
							{hasTelegramConnection ? null : (
								<Button size="sm" onClick={() => startPairing("telegram")}>
									Pair Telegram Chat
								</Button>
							)}
							<Button
								size="sm"
								variant="secondary"
								className={refreshButtonClassName}
								onClick={() => refreshPlatform("telegram")}
								disabled={isRefreshing("telegram")}
							>
								<RefreshCw className={refreshIconClassName("telegram")} />
								Refresh
							</Button>
						</div>

						{hasTelegramConnection ? null : renderPairingPanel("telegram")}
						<Separator className="bg-accent" />
						{renderConnectionRows("telegram", "No Telegram chats connected yet.")}
					</CardContent>
				</Card>
			) : null}

			{!gatewayDisabled && slackGatewayEnabled ? (
				<Card className="order-4 group relative h-full overflow-hidden border-accent bg-accent/20 transition-all duration-200 hover:shadow-md">
					<CardHeader className="space-y-1.5 p-4 pb-2">
						<div className="flex items-center justify-between gap-3">
							<CardTitle className="flex items-center gap-2 text-sm">Slack</CardTitle>
						</div>
						<p className="text-xs text-muted-foreground">
							Enable the SurfSense Slack bot so teammates can mention it in Slack.
						</p>
					</CardHeader>
					<CardContent className="space-y-3 p-4 pt-0">
						<div className="flex flex-wrap gap-2">
							<Button size="sm" onClick={installSlackGateway}>
								Add Slack Workspace
							</Button>
							<Button
								size="sm"
								variant="secondary"
								className={refreshButtonClassName}
								onClick={() => refreshPlatform("slack")}
								disabled={isRefreshing("slack")}
							>
								<RefreshCw className={refreshIconClassName("slack")} />
								Refresh
							</Button>
						</div>
						<Separator className="bg-accent" />
						{renderConnectionRows("slack", "No Slack workspaces connected yet.")}
					</CardContent>
				</Card>
			) : null}

			{!gatewayDisabled && discordGatewayEnabled ? (
				<Card className="order-3 group relative h-full overflow-hidden border-accent bg-accent/20 transition-all duration-200 hover:shadow-md">
					<CardHeader className="space-y-1.5 p-4 pb-2">
						<div className="flex items-center justify-between gap-3">
							<CardTitle className="flex items-center gap-2 text-sm">Discord</CardTitle>
						</div>
						<p className="text-xs text-muted-foreground">
							Enable the SurfSense Discord bot so teammates can mention it in Discord.
						</p>
					</CardHeader>
					<CardContent className="space-y-3 p-4 pt-0">
						<div className="flex flex-wrap gap-2">
							<Button size="sm" onClick={installDiscordGateway}>
								Add Discord Server
							</Button>
							<Button
								size="sm"
								variant="secondary"
								className={refreshButtonClassName}
								onClick={() => refreshPlatform("discord")}
								disabled={isRefreshing("discord")}
							>
								<RefreshCw className={refreshIconClassName("discord")} />
								Refresh
							</Button>
						</div>
						<Separator className="bg-accent" />
						{renderConnectionRows("discord", "No Discord servers connected yet.")}
					</CardContent>
				</Card>
			) : null}

			{!gatewayDisabled && whatsappMode !== "disabled" ? (
				<Card className="order-2 group relative h-full overflow-hidden border-accent bg-accent/20 transition-all duration-200 hover:shadow-md">
					<CardHeader className="space-y-1.5 p-4 pb-2">
						<div className="flex items-center justify-between gap-3">
							<CardTitle className="flex items-center gap-2 text-sm">WhatsApp</CardTitle>
						</div>
						<p className="text-xs text-muted-foreground">
							{whatsappMode === "baileys"
								? 'Use "Message Yourself". Other chats are ignored.'
								: "Connect WhatsApp to chat with Surfsense."}
						</p>
					</CardHeader>
					<CardContent className="space-y-3 p-4 pt-0">
						{whatsappMode === "cloud" ? (
							<div className="space-y-3">
								<div className="flex flex-wrap gap-2">
									{hasWhatsAppConnection ? null : (
										<Button size="sm" onClick={() => startPairing("whatsapp")}>
											Pair WhatsApp
										</Button>
									)}
									<Button
										size="sm"
										variant="secondary"
										className={refreshButtonClassName}
										onClick={() => refreshPlatform("whatsapp")}
										disabled={isRefreshing("whatsapp")}
									>
										<RefreshCw className={refreshIconClassName("whatsapp")} />
										Refresh
									</Button>
								</div>
								{hasWhatsAppConnection ? null : renderPairingPanel("whatsapp")}
							</div>
						) : null}
						{whatsappMode === "baileys" ? (
							<div className="space-y-3">
								<Button
									size="sm"
									variant="secondary"
									className={refreshButtonClassName}
									onClick={refreshBaileys}
									disabled={isRefreshing("whatsapp")}
								>
									<RefreshCw className={refreshIconClassName("whatsapp")} />
									Refresh
								</Button>
								{baileysQr ? (
									<div className="rounded-lg border border-accent bg-accent/20 p-3">
										<p className="text-sm font-medium">WhatsApp QR pairing</p>
										<p className="mt-1 text-xs text-muted-foreground">
											Scan this QR from WhatsApp &gt; Linked Devices &gt; Link a Device.
										</p>
										<div className="mt-3 inline-block rounded-md bg-white p-3">
											<QRCodeSVG value={baileysQr} size={192} />
										</div>
									</div>
								) : null}
								{baileysHealth ? (
									<p className="text-xs text-muted-foreground">
										Bridge status: {baileysHealth.status}
										{typeof baileysHealth.queueDepth === "number"
											? `, queue: ${baileysHealth.queueDepth}`
											: ""}
									</p>
								) : null}
							</div>
						) : null}
						<Separator className="bg-accent" />
						{renderConnectionRows("whatsapp", "No WhatsApp chats connected yet.")}
					</CardContent>
				</Card>
			) : null}
		</div>
	);
}
