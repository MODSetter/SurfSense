"use client";

import { MessageCircle, RefreshCw, ShieldAlert } from "lucide-react";
import { useParams } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { useCallback, useEffect, useState, useTransition } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { SearchSpace } from "@/contracts/types/search-space.types";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";
import { BACKEND_URL } from "@/lib/env-config";

type GatewayConnection = {
	id: number;
	platform: string;
	state: string;
	search_space_id: number;
	display_name?: string | null;
	external_username?: string | null;
	workspace_name?: string | null;
	workspace_id?: string | null;
	health_status: string;
	suspended_reason?: string | null;
};

type Platform = {
	id: number;
	platform: string;
	mode: string;
	bot_username?: string | null;
	health_status: string;
	last_health_check_at?: string | null;
};

type Pairing = {
	binding_id: number;
	code: string;
	deep_link: string;
	expires_at: string;
};

type PairingPlatform = "telegram" | "whatsapp";

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
	const whatsappMode = process.env.NEXT_PUBLIC_GATEWAY_WHATSAPP_INTAKE_MODE ?? "disabled";
	const slackGatewayEnabled = process.env.NEXT_PUBLIC_GATEWAY_SLACK_ENABLED === "true";
	const discordGatewayEnabled = process.env.NEXT_PUBLIC_GATEWAY_DISCORD_ENABLED === "true";
	const [connections, setConnections] = useState<GatewayConnection[]>([]);
	const [platforms, setPlatforms] = useState<Platform[]>([]);
	const [searchSpaces, setSearchSpaces] = useState<SearchSpace[]>([]);
	const [pairing, setPairing] = useState<Pairing | null>(null);
	const [pairingPlatform, setPairingPlatform] = useState<PairingPlatform | null>(null);
	const [baileysHealth, setBaileysHealth] = useState<BaileysHealth | null>(null);
	const [loading, setLoading] = useState(true);
	const [isPending, startTransition] = useTransition();

	const refresh = useCallback(async () => {
		setLoading(true);
		const [connectionsRes, platformsRes, spaces] = await Promise.all([
			authenticatedFetch(`${BACKEND_URL}/api/v1/gateway/connections`),
			authenticatedFetch(`${BACKEND_URL}/api/v1/gateway/platforms`),
			searchSpacesApiService.getSearchSpaces(),
		]);
		setConnections(await connectionsRes.json());
		setPlatforms(await platformsRes.json());
		setSearchSpaces(spaces);
		setLoading(false);
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const refreshBaileysHealth = useCallback(async () => {
		if (whatsappMode !== "baileys") return;
		const res = await authenticatedFetch(`${BACKEND_URL}/api/v1/gateway/whatsapp/baileys/health`);
		if (!res.ok) return;
		const data = (await res.json()) as BaileysHealth;
		setBaileysHealth(data);
	}, [whatsappMode]);

	useEffect(() => {
		void refreshBaileysHealth();
	}, [refreshBaileysHealth]);

	async function startPairing(platform: PairingPlatform) {
		const res = await authenticatedFetch(`${BACKEND_URL}/api/v1/gateway/bindings/start`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ platform, search_space_id: searchSpaceId }),
		});
		setPairing(await res.json());
		setPairingPlatform(platform);
		await refresh();
	}

	async function installSlackGateway() {
		const res = await authenticatedFetch(
			`${BACKEND_URL}/api/v1/gateway/slack/install?search_space_id=${searchSpaceId}`
		);
		if (!res.ok) return;
		const data = (await res.json()) as { auth_url?: string };
		if (data.auth_url) {
			window.location.href = data.auth_url;
		}
	}

	async function installDiscordGateway() {
		const res = await authenticatedFetch(
			`${BACKEND_URL}/api/v1/gateway/discord/install?search_space_id=${searchSpaceId}`
		);
		if (!res.ok) return;
		const data = (await res.json()) as { auth_url?: string };
		if (data.auth_url) {
			window.location.href = data.auth_url;
		}
	}

	function refreshBaileys() {
		startTransition(async () => {
			await refreshBaileysHealth();
			await refresh();
		});
	}

	async function revoke(id: number) {
		await authenticatedFetch(`${BACKEND_URL}/api/v1/gateway/bindings/${id}`, {
			method: "DELETE",
		});
		await refresh();
	}

	async function updateConnectionSearchSpace(id: number, nextSearchSpaceId: string) {
		const previousConnections = connections;
		const parsedSearchSpaceId = Number(nextSearchSpaceId);
		setConnections((current) =>
			current.map((connection) =>
				connection.id === id ? { ...connection, search_space_id: parsedSearchSpaceId } : connection
			)
		);
		const res = await authenticatedFetch(
			`${BACKEND_URL}/api/v1/gateway/bindings/${id}/search-space`,
			{
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ search_space_id: parsedSearchSpaceId }),
			}
		);
		if (!res.ok) {
			setConnections(previousConnections);
			toast.error("Failed to update messaging route");
			return;
		}
		toast.success("Messaging route updated");
		await refresh();
	}

	async function resume(id: number) {
		await authenticatedFetch(`${BACKEND_URL}/api/v1/gateway/bindings/${id}/resume`, {
			method: "POST",
		});
		await refresh();
	}

	const telegram = platforms.find((p) => p.platform === "telegram");
	const whatsapp = platforms.find((p) => p.platform === "whatsapp");
	const slack = platforms.find((p) => p.platform === "slack");
	const discord = platforms.find((p) => p.platform === "discord");
	const baileysQr = baileysHealth?.qr || null;
	const currentSearchSpaceName =
		searchSpaces.find((space) => space.id === searchSpaceId)?.name || "this search space";
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
		connection.workspace_name ||
		connection.display_name ||
		connection.external_username ||
		`${platformLabel(connection.platform)} connection`;
	const renderPairingPanel = (platform: PairingPlatform) => {
		if (!pairing || pairingPlatform !== platform) return null;

		return (
			<div className="rounded-md border border-border bg-muted/30 p-4">
				<p className="text-sm font-medium">Pairing code</p>
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

	return (
		<div className="space-y-5">
			<Card>
				<CardHeader className="space-y-2">
					<div className="flex items-center justify-between gap-3">
						<CardTitle className="flex items-center gap-2 text-base">
							<MessageCircle className="h-4 w-4" />
							Telegram
						</CardTitle>
						<Badge variant={telegram?.health_status === "ok" ? "default" : "secondary"}>
							{telegram?.health_status ?? "not configured"}
						</Badge>
					</div>
					<p className="text-sm text-muted-foreground">
						Pair a Telegram chat with this search space. Telegram conversations stay in Telegram and
						are not mirrored in SurfSense chat history.
					</p>
				</CardHeader>
				<CardContent className="space-y-4">
					<div className="flex flex-wrap gap-2">
						<Button onClick={() => startPairing("telegram")}>Pair Telegram Chat</Button>
						<Button variant="outline" onClick={refresh} disabled={loading}>
							<RefreshCw className="mr-2 h-4 w-4" />
							Refresh
						</Button>
					</div>

					{renderPairingPanel("telegram")}
				</CardContent>
			</Card>

			{slackGatewayEnabled ? (
				<Card>
					<CardHeader className="space-y-2">
						<div className="flex items-center justify-between gap-3">
							<CardTitle className="flex items-center gap-2 text-base">
								<MessageCircle className="h-4 w-4" />
								Slack Bot
							</CardTitle>
							<Badge variant={slack?.health_status === "ok" ? "default" : "secondary"}>
								{slack ? "enabled" : "not enabled"}
							</Badge>
						</div>
						<p className="text-sm text-muted-foreground">
							Enable the SurfSense Slack bot so teammates can mention it in Slack. This is separate
							from the Slack search connector.
						</p>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="flex flex-wrap gap-2">
							<Button onClick={installSlackGateway}>Add Slack Workspace</Button>
							<Button variant="outline" onClick={refresh} disabled={loading}>
								<RefreshCw className="mr-2 h-4 w-4" />
								Refresh
							</Button>
						</div>
						<p className="text-xs text-muted-foreground">
							New Slack workspace connections will route to {currentSearchSpaceName} first. You can
							change each connection's search space below.
						</p>
					</CardContent>
				</Card>
			) : null}

			{discordGatewayEnabled ? (
				<Card>
					<CardHeader className="space-y-2">
						<div className="flex items-center justify-between gap-3">
							<CardTitle className="flex items-center gap-2 text-base">
								<MessageCircle className="h-4 w-4" />
								Discord Bot
							</CardTitle>
							<Badge variant={discord?.health_status === "ok" ? "default" : "secondary"}>
								{discord ? "enabled" : "not enabled"}
							</Badge>
						</div>
						<p className="text-sm text-muted-foreground">
							Enable the SurfSense Discord bot so teammates can mention it in Discord. This is
							separate from the Discord connector.
						</p>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="flex flex-wrap gap-2">
							<Button onClick={installDiscordGateway}>Add Discord Server</Button>
							<Button variant="outline" onClick={refresh} disabled={loading}>
								<RefreshCw className="mr-2 h-4 w-4" />
								Refresh
							</Button>
						</div>
						<p className="text-xs text-muted-foreground">
							New Discord server connections will route to {currentSearchSpaceName} first. You can
							change each connection's search space below.
						</p>
					</CardContent>
				</Card>
			) : null}

			{whatsappMode !== "disabled" ? (
				<Card>
					<CardHeader className="space-y-2">
						<div className="flex items-center justify-between gap-3">
							<CardTitle className="flex items-center gap-2 text-base">
								<MessageCircle className="h-4 w-4" />
								WhatsApp
							</CardTitle>
							<Badge variant={whatsapp?.health_status === "ok" ? "default" : "secondary"}>
								{whatsapp?.health_status ?? "not configured"}
							</Badge>
						</div>
						<p className="text-sm text-muted-foreground">
							Pair this search space with WhatsApp using the configured gateway mode.
						</p>
					</CardHeader>
					<CardContent className="space-y-4">
						{whatsappMode === "cloud" ? (
							<div className="space-y-3">
								<Button onClick={() => startPairing("whatsapp")}>Pair WhatsApp</Button>
								{renderPairingPanel("whatsapp")}
							</div>
						) : null}
						{whatsappMode === "baileys" ? (
							<div className="space-y-3">
								<p className="text-sm text-muted-foreground">
									Self-hosted WhatsApp uses Message Yourself mode. After pairing, send messages in
									your own WhatsApp chat with yourself; messages from other chats are ignored.
								</p>
								<Button variant="outline" onClick={refreshBaileys} disabled={isPending}>
									Refresh WhatsApp Bridge
								</Button>
								{baileysQr ? (
									<div className="rounded-md border border-border bg-muted/30 p-4">
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
					</CardContent>
				</Card>
			) : null}

			<Card>
				<CardHeader>
					<CardTitle className="text-base">Connected Messaging Channels</CardTitle>
					<p className="text-sm text-muted-foreground">
						Choose which search space each external channel should use when messages arrive.
					</p>
				</CardHeader>
				<CardContent className="space-y-3">
					{connections.length === 0 ? (
						<p className="text-sm text-muted-foreground">No messaging channels connected yet.</p>
					) : (
						connections.map((connection) => (
							<div
								key={connection.id}
								className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3"
							>
								<div className="min-w-0">
									<p className="text-sm font-medium">{connectionTitle(connection)}</p>
									<p className="text-xs text-muted-foreground">
										{platformLabel(connection.platform)}
										{connection.external_username ? ` · ${connection.external_username}` : ""}
										{connection.state ? ` · ${connection.state}` : ""}
									</p>
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
										onValueChange={(value) => updateConnectionSearchSpace(connection.id, value)}
										disabled={searchSpaces.length === 0 || isPending}
									>
										<SelectTrigger className="w-[220px]">
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
										<Button size="sm" variant="outline" onClick={() => resume(connection.id)}>
											Resume
										</Button>
									) : null}
									<Button size="sm" variant="destructive" onClick={() => revoke(connection.id)}>
										Disconnect
									</Button>
								</div>
							</div>
						))
					)}
				</CardContent>
			</Card>
		</div>
	);
}
