"use client";

import { useQuery as useZeroQuery } from "@rocicorp/zero/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CreditCard, RefreshCw } from "lucide-react";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { AppError } from "@/lib/error";
import { getWorkspaceIdNumber } from "@/lib/route-params";
import { queries } from "@/zero/queries";

const microsToDollars = (micros: number | null | undefined): string => {
	if (micros == null) return "";
	return (micros / 1_000_000).toString();
};

const dollarsToMicros = (value: string): number | null => {
	const trimmed = value.trim();
	if (trimmed === "") return null;
	const dollars = Number(trimmed);
	if (!Number.isFinite(dollars) || dollars < 0) return null;
	return Math.round(dollars * 1_000_000);
};

const formatUsd = (micros: number) => `$${(Math.max(0, micros) / 1_000_000).toFixed(2)}`;

export function AutoReloadSettings() {
	const params = useParams();
	const router = useRouter();
	const pathname = usePathname();
	const searchParams = useSearchParams();
	const queryClient = useQueryClient();
	const workspaceId = getWorkspaceIdNumber(params) ?? 0;

	const [enabled, setEnabled] = useState(false);
	const [thresholdInput, setThresholdInput] = useState("");
	const [amountInput, setAmountInput] = useState("");
	const seededRef = useRef(false);

	const [me] = useZeroQuery(queries.user.me({}));
	const balanceMicros = me?.creditMicrosBalance ?? 0;

	const { data: settings, isLoading } = useQuery({
		queryKey: ["auto-reload-settings"],
		queryFn: () => stripeApiService.getAutoReloadSettings(),
	});

	// Seed the form once from the server, then let the user own the inputs.
	useEffect(() => {
		if (settings && !seededRef.current) {
			seededRef.current = true;
			setEnabled(settings.enabled);
			setThresholdInput(microsToDollars(settings.threshold_micros));
			setAmountInput(microsToDollars(settings.amount_micros));
		}
	}, [settings]);

	// Surface the result of the Stripe card-setup redirect.
	useEffect(() => {
		const setupResult = searchParams.get("auto_reload_setup");
		if (!setupResult) return;
		if (setupResult === "success") {
			toast.success("Card saved. You can now enable auto-reload.");
			queryClient.invalidateQueries({ queryKey: ["auto-reload-settings"] });
		} else if (setupResult === "cancel") {
			toast.info("Card setup canceled.");
		}
		// Strip the query param so refreshes don't re-toast.
		router.replace(pathname);
	}, [searchParams, router, pathname, queryClient]);

	const setupMutation = useMutation({
		mutationFn: () => stripeApiService.createAutoReloadSetupSession({ workspace_id: workspaceId }),
		onSuccess: (response) => {
			window.location.assign(response.checkout_url);
		},
		onError: () => {
			toast.error("Couldn't start card setup. Please try again.");
		},
	});

	const saveMutation = useMutation({
		mutationFn: stripeApiService.updateAutoReloadSettings,
		onSuccess: (updated) => {
			queryClient.setQueryData(["auto-reload-settings"], updated);
			toast.success(updated.enabled ? "Auto-reload is on." : "Auto-reload settings saved.");
		},
		onError: (error) => {
			if (error instanceof AppError && error.message) {
				toast.error(error.message);
				return;
			}
			toast.error("Couldn't save auto-reload settings. Please try again.");
		},
	});

	// Render nothing while loading (avoids a spinner flash on pages where the
	// feature flag turns out to be off) and when auto-reload is disabled
	// server-side.
	if (isLoading || !settings || !settings.feature_enabled) {
		return null;
	}

	const minAmountDollars = (settings.min_amount_micros / 1_000_000).toFixed(2);
	const hasCard = settings.has_payment_method;

	const handleSave = () => {
		if (!enabled) {
			saveMutation.mutate({
				enabled: false,
				threshold_micros: dollarsToMicros(thresholdInput),
				amount_micros: dollarsToMicros(amountInput),
			});
			return;
		}

		const thresholdMicros = dollarsToMicros(thresholdInput);
		const amountMicros = dollarsToMicros(amountInput);

		if (!thresholdMicros || thresholdMicros <= 0) {
			toast.error("Enter a low-balance threshold greater than $0.");
			return;
		}
		if (amountMicros == null || amountMicros < settings.min_amount_micros) {
			toast.error(`Reload amount must be at least $${minAmountDollars}.`);
			return;
		}

		saveMutation.mutate({
			enabled: true,
			threshold_micros: thresholdMicros,
			amount_micros: amountMicros,
		});
	};

	return (
		<Card>
			<CardHeader>
				<CardTitle className="flex items-center gap-2 text-base">
					<RefreshCw className="h-4 w-4 text-amber-500" />
					Auto-reload
				</CardTitle>
				<CardDescription>
					Automatically top up your credit balance when it drops below a threshold, using a saved
					card. Current balance:{" "}
					<span className="font-medium text-foreground">{formatUsd(balanceMicros)}</span>.
				</CardDescription>
			</CardHeader>
			<CardContent className="space-y-5">
				{settings.failed_at && (
					<Alert variant="destructive">
						<AlertTriangle className="h-4 w-4" />
						<AlertTitle>Last auto-reload failed</AlertTitle>
						<AlertDescription>
							Your saved card was declined and auto-reload was turned off. Update your card and
							re-enable it below to keep topping up automatically.
						</AlertDescription>
					</Alert>
				)}

				{!hasCard ? (
					<div className="flex flex-col items-start gap-3 rounded-lg border bg-muted/20 p-4">
						<div className="flex items-center gap-2 text-sm">
							<CreditCard className="h-4 w-4 text-muted-foreground" />
							<span>Add a card to enable automatic top-ups.</span>
						</div>
						<Button onClick={() => setupMutation.mutate()} disabled={setupMutation.isPending}>
							{setupMutation.isPending ? (
								<>
									<Spinner size="xs" />
									Redirecting
								</>
							) : (
								"Add a card"
							)}
						</Button>
					</div>
				) : (
					<>
						<div className="flex items-center justify-between gap-4">
							<div className="space-y-0.5">
								<Label htmlFor="auto-reload-toggle" className="text-sm font-medium">
									Enable auto-reload
								</Label>
								<p className="text-xs text-muted-foreground">
									Charge your saved card when the balance gets low.
								</p>
							</div>
							<Switch id="auto-reload-toggle" checked={enabled} onCheckedChange={setEnabled} />
						</div>

						<div className="grid gap-4 sm:grid-cols-2">
							<div className="space-y-1.5">
								<Label htmlFor="auto-reload-threshold" className="text-xs">
									When balance falls below
								</Label>
								<div className="relative">
									<span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
										$
									</span>
									<Input
										id="auto-reload-threshold"
										type="number"
										min="0"
										step="1"
										inputMode="decimal"
										className="pl-6 tabular-nums"
										value={thresholdInput}
										onChange={(e) => setThresholdInput(e.target.value)}
										disabled={!enabled}
										placeholder="5"
									/>
								</div>
							</div>
							<div className="space-y-1.5">
								<Label htmlFor="auto-reload-amount" className="text-xs">
									Add this much credit
								</Label>
								<div className="relative">
									<span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
										$
									</span>
									<Input
										id="auto-reload-amount"
										type="number"
										min={minAmountDollars}
										step="1"
										inputMode="decimal"
										className="pl-6 tabular-nums"
										value={amountInput}
										onChange={(e) => setAmountInput(e.target.value)}
										disabled={!enabled}
										placeholder="10"
									/>
								</div>
								<p className="text-[11px] text-muted-foreground">Minimum ${minAmountDollars}.</p>
							</div>
						</div>

						<div className="flex items-center justify-between gap-3">
							<Button
								variant="ghost"
								size="sm"
								className="text-muted-foreground"
								onClick={() => setupMutation.mutate()}
								disabled={setupMutation.isPending}
							>
								<CreditCard className="h-3.5 w-3.5" />
								Update card
							</Button>
							<Button onClick={handleSave} disabled={saveMutation.isPending}>
								{saveMutation.isPending ? (
									<>
										<Spinner size="xs" />
										Saving
									</>
								) : (
									"Save"
								)}
							</Button>
						</div>
					</>
				)}
			</CardContent>
		</Card>
	);
}
