"use client";

import { useId, useState } from "react";
import { HomeButton } from "@/components/homepage/home/home-button";
import { Spinner } from "@/components/ui/spinner";
import { buildBackendUrl } from "@/lib/env-config";

/**
 * The two forms on `/license`, each rendered in its own section on the page
 * (`page.tsx`): the trial is the one most visitors want and gets the primary
 * button; resending an existing license is secondary.
 *
 * Built from the same `ss-home-*` primitives as the rest of the site design:
 * a flush hairline-bordered panel rather than a floating shadcn `Card`, and
 * plain inputs styled like the blog search box, so this page reads as part of
 * the same document as the homepage and pricing rather than an older surface
 * left behind.
 */

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

function EmailField({
	id,
	value,
	onChange,
}: {
	id: string;
	value: string;
	onChange: (value: string) => void;
}) {
	return (
		<div className="flex flex-col gap-2">
			<label htmlFor={id} className="text-sm font-medium">
				Email address
			</label>
			<input
				id={id}
				type="email"
				autoComplete="email"
				placeholder="you@company.com"
				value={value}
				onChange={(event) => onChange(event.target.value)}
				required
				className="w-full rounded-(--radius) border border-border bg-background px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
			/>
		</div>
	);
}

/**
 * The form itself, unlabelled and unboxed: each one now sits under its own
 * section heading (`Start a trial`, `Get your license again`), which already
 * marks it off from the section before and after, so a border around the
 * form too would be a second frame around the same thing.
 */
function FormPanel({ description, children }: { description: string; children: React.ReactNode }) {
	return (
		<div>
			<p className="ss-home-body text-sm">{description}</p>
			<div className="mt-5">{children}</div>
		</div>
	);
}

export function ResendForm() {
	const id = useId();
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
		<FormPanel description="Enter the email address you bought with. We will send your license file back to that inbox.">
			<form onSubmit={handleSubmit} className="flex flex-col gap-4">
				<EmailField id={`resend-email-${id}`} value={email} onChange={setEmail} />
				<HomeButton type="submit" disabled={busy} variant="secondary" className="self-start">
					{busy ? <Spinner size="sm" /> : null}
					{busy ? "Sending" : "Send my license"}
				</HomeButton>
				{outcome ? (
					<p
						className={outcome.kind === "ok" ? "ss-home-body text-sm" : "text-sm text-destructive"}
					>
						{outcome.message}
					</p>
				) : null}
			</form>
		</FormPanel>
	);
}

export function TrialForm() {
	const id = useId();
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
		<FormPanel description="One trial per email address. We will send the license file to your inbox.">
			<form onSubmit={handleSubmit} className="flex flex-col gap-4">
				<EmailField id={`trial-email-${id}`} value={email} onChange={setEmail} />
				<HomeButton type="submit" disabled={busy} className="self-start">
					{busy ? <Spinner size="sm" /> : null}
					{busy ? "Sending" : "Email me a trial"}
				</HomeButton>
				{outcome ? (
					<p
						className={outcome.kind === "ok" ? "ss-home-body text-sm" : "text-sm text-destructive"}
					>
						{outcome.message}
					</p>
				) : null}
			</form>
		</FormPanel>
	);
}
