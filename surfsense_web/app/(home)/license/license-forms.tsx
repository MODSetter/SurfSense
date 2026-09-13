"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { buildBackendUrl } from "@/lib/env-config";

type Outcome = { kind: "ok" | "error"; message: string } | null;

/**
 * Resend deliberately answers the same whether it found licenses or none, so
 * it cannot be used to learn who is a customer. The page therefore cannot tell
 * the user "no license found" -- the copy has to carry that ambiguity, or a
 * typo looks like success with no explanation.
 */
const RESEND_SENT =
	"If a license is registered to that address, it is on its way. " +
	"Check your spam folder, and make sure you used the exact address you paid with.";

const TRIAL_SENT = "Your trial license is on its way. Check your spam folder too.";

// 503 covers either half being down -- the license service or the mail
// server -- so this must not blame email specifically.
const SERVICE_DOWN = "Something on our side is unavailable. Please try again in a few minutes.";

const RATE_LIMITED = "Too many requests from here. Please try again later.";

async function postEmail(path: string, email: string): Promise<Response> {
	return fetch(buildBackendUrl(path), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ email }),
	});
}

function ResendForm() {
	const [email, setEmail] = useState("");
	const [busy, setBusy] = useState(false);
	const [outcome, setOutcome] = useState<Outcome>(null);

	async function handleSubmit(event: React.FormEvent) {
		event.preventDefault();
		if (busy || !email.trim()) return;

		setBusy(true);
		setOutcome(null);
		try {
			const response = await postEmail("/api/v1/license/resend", email.trim());
			if (response.ok) {
				setOutcome({ kind: "ok", message: RESEND_SENT });
			} else if (response.status === 429) {
				setOutcome({ kind: "error", message: RATE_LIMITED });
			} else if (response.status === 503) {
				setOutcome({ kind: "error", message: SERVICE_DOWN });
			} else if (response.status === 422) {
				setOutcome({ kind: "error", message: "That does not look like an email address." });
			} else {
				setOutcome({ kind: "error", message: "Something went wrong. Please try again." });
			}
		} catch {
			setOutcome({ kind: "error", message: "Could not reach SurfSense. Check your connection." });
		} finally {
			setBusy(false);
		}
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle>Get your license file again</CardTitle>
				<CardDescription>
					Enter the email address you bought with. We will send your license file back to that same
					address.
				</CardDescription>
			</CardHeader>
			<CardContent>
				<form onSubmit={handleSubmit} className="flex flex-col gap-4">
					<div className="flex flex-col gap-2">
						<Label htmlFor="resend-email">Email address</Label>
						<Input
							id="resend-email"
							type="email"
							autoComplete="email"
							placeholder="you@company.com"
							value={email}
							onChange={(event) => setEmail(event.target.value)}
							required
						/>
					</div>
					<Button type="submit" disabled={busy} className="self-start">
						{busy ? <Spinner /> : null}
						{busy ? "Sending" : "Send my license"}
					</Button>
					{outcome ? (
						<p
							className={
								outcome.kind === "ok" ? "text-sm text-muted-foreground" : "text-sm text-destructive"
							}
						>
							{outcome.message}
						</p>
					) : null}
				</form>
			</CardContent>
		</Card>
	);
}

function TrialForm() {
	const [email, setEmail] = useState("");
	const [busy, setBusy] = useState(false);
	const [outcome, setOutcome] = useState<Outcome>(null);

	async function handleSubmit(event: React.FormEvent) {
		event.preventDefault();
		if (busy || !email.trim()) return;

		setBusy(true);
		setOutcome(null);
		try {
			const response = await postEmail("/api/v1/license/trial", email.trim());
			if (response.ok) {
				setOutcome({ kind: "ok", message: TRIAL_SENT });
			} else if (response.status === 409) {
				// Unlike resend, trial can report its outcome: it has to say
				// "already claimed", so there is nothing to keep secret.
				setOutcome({
					kind: "error",
					message: "A trial has already been claimed for that address.",
				});
			} else if (response.status === 400) {
				setOutcome({
					kind: "error",
					message: "Please use a permanent email address, not a disposable one.",
				});
			} else if (response.status === 404) {
				setOutcome({ kind: "error", message: "Trials are not open yet. Check back shortly." });
			} else if (response.status === 429) {
				setOutcome({ kind: "error", message: RATE_LIMITED });
			} else if (response.status === 503) {
				setOutcome({ kind: "error", message: SERVICE_DOWN });
			} else if (response.status === 422) {
				setOutcome({ kind: "error", message: "That does not look like an email address." });
			} else {
				setOutcome({ kind: "error", message: "Something went wrong. Please try again." });
			}
		} catch {
			setOutcome({ kind: "error", message: "Could not reach SurfSense. Check your connection." });
		} finally {
			setBusy(false);
		}
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle>Start a 14-day trial</CardTitle>
				<CardDescription>
					One trial per email address. We will send the license file to the address you enter.
				</CardDescription>
			</CardHeader>
			<CardContent>
				<form onSubmit={handleSubmit} className="flex flex-col gap-4">
					<div className="flex flex-col gap-2">
						<Label htmlFor="trial-email">Email address</Label>
						<Input
							id="trial-email"
							type="email"
							autoComplete="email"
							placeholder="you@company.com"
							value={email}
							onChange={(event) => setEmail(event.target.value)}
							required
						/>
					</div>
					<Button type="submit" disabled={busy} variant="secondary" className="self-start">
						{busy ? <Spinner /> : null}
						{busy ? "Sending" : "Email me a trial"}
					</Button>
					{outcome ? (
						<p
							className={
								outcome.kind === "ok" ? "text-sm text-muted-foreground" : "text-sm text-destructive"
							}
						>
							{outcome.message}
						</p>
					) : null}
				</form>
			</CardContent>
		</Card>
	);
}

export function LicenseForms() {
	return (
		<div className="flex flex-col gap-6">
			<ResendForm />
			<TrialForm />
		</div>
	);
}
