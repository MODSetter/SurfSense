"use client";

import { MessageCircle, RefreshCw, ShieldAlert } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState, useTransition } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { authenticatedFetch } from "@/lib/auth-utils";
import { BACKEND_URL } from "@/lib/env-config";

type Binding = {
	id: number;
	platform?: string;
	state: string;
	search_space_id: number;
	external_display_name?: string | null;
	external_username?: string | null;
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

export function MessagingChannelsContent() {
	const params = useParams<{ search_space_id: string }>();
	const searchSpaceId = Number(params.search_space_id);
	const [bindings, setBindings] = useState<Binding[]>([]);
	const [platforms, setPlatforms] = useState<Platform[]>([]);
	const [pairing, setPairing] = useState<Pairing | null>(null);
	const [pairingPlatform, setPairingPlatform] = useState<PairingPlatform | null>(null);
	const [whatsappStatus, setWhatsappStatus] = useState<string | null>(null);
	const [baileysPhone, setBaileysPhone] = useState("");
	const [baileysCode, setBaileysCode] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [isPending, startTransition] = useTransition();

	const refresh = useCallback(async () => {
		setLoading(true);
		const [bindingsRes, platformsRes] = await Promise.all([
			authenticatedFetch(`${BACKEND_URL}/api/v1/gateway/bindings`),
			authenticatedFetch(`${BACKEND_URL}/api/v1/gateway/platforms`),
		]);
		setBindings(await bindingsRes.json());
		setPlatforms(await platformsRes.json());
		setLoading(false);
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

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

	function pairBaileys() {
		startTransition(async () => {
			setWhatsappStatus("Requesting WhatsApp pairing code...");
			const res = await authenticatedFetch(`${BACKEND_URL}/api/v1/gateway/whatsapp/baileys/pair`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ search_space_id: searchSpaceId, phone_number: baileysPhone }),
			});
			if (!res.ok) {
				setWhatsappStatus("Unable to request pairing code. Check the whatsapp-bridge service.");
				return;
			}
			const data = await res.json();
			setBaileysCode(data.pairing_code ?? null);
			setWhatsappStatus(
				data.status === "connected"
					? "WhatsApp bridge is connected."
					: "Enter the pairing code in WhatsApp.",
			);
			await refresh();
		});
	}

	async function revoke(id: number) {
		await authenticatedFetch(`${BACKEND_URL}/api/v1/gateway/bindings/${id}`, {
			method: "DELETE",
		});
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
	const whatsappMode = process.env.NEXT_PUBLIC_GATEWAY_WHATSAPP_INTAKE_MODE ?? "disabled";
	const activeBindings = bindings.filter((binding) => binding.search_space_id === searchSpaceId);
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
								<input
									className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
									placeholder="Phone number with country code, e.g. 15551234567"
									value={baileysPhone}
									onChange={(event) => setBaileysPhone(event.target.value)}
								/>
								<Button onClick={pairBaileys} disabled={isPending || !baileysPhone.trim()}>
									Pair WhatsApp
								</Button>
								{baileysCode ? (
									<div className="rounded-md border border-border bg-muted/30 p-4">
										<p className="text-sm font-medium">WhatsApp pairing code</p>
										<p className="mt-2 font-mono text-lg">{baileysCode}</p>
									</div>
								) : null}
							</div>
						) : null}
						{whatsappStatus ? (
							<p className="text-sm text-muted-foreground">{whatsappStatus}</p>
						) : null}
					</CardContent>
				</Card>
			) : null}

			<Card>
				<CardHeader>
					<CardTitle className="text-base">Active Chats</CardTitle>
				</CardHeader>
				<CardContent className="space-y-3">
					{activeBindings.length === 0 ? (
						<p className="text-sm text-muted-foreground">No external chats connected yet.</p>
					) : (
						activeBindings.map((binding) => (
							<div
								key={binding.id}
								className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3"
							>
								<div>
									<p className="text-sm font-medium">
										{binding.external_display_name ||
											binding.external_username ||
											`Binding ${binding.id}`}
									</p>
									<p className="text-xs text-muted-foreground">{binding.state}</p>
									{binding.suspended_reason ? (
										<p className="mt-1 flex items-center gap-1 text-xs text-destructive">
											<ShieldAlert className="h-3 w-3" />
											{binding.suspended_reason}
										</p>
									) : null}
								</div>
								<div className="flex gap-2">
									{binding.state === "suspended" ? (
										<Button size="sm" variant="outline" onClick={() => resume(binding.id)}>
											Resume
										</Button>
									) : null}
									<Button size="sm" variant="destructive" onClick={() => revoke(binding.id)}>
										Revoke
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
