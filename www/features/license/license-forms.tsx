"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { HomeButton } from "@/components/site/home-button";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { Spinner } from "@/components/ui/spinner";
import { currentChannel } from "@/features/funnel-attribution/current-channel";
import { trackTrialRequested } from "@/features/funnel-attribution/funnel-events";
import { trialOutcome } from "@/features/funnel-attribution/trial-outcome";
import { buildBackendUrl } from "@/features/license/backend-url";

/**
 * The two license forms, now on separate pages. `ResendForm` is the whole of
 * `/license` (`page.tsx`), sitting in its hero as that page's one action.
 * `TrialForm` is claimed on `/downloads` instead, because the 30-day licence
 * is part of the free plan and a licence file is inert without the app the
 * same page hands you.
 *
 * Both are the same `EmailPill`, the homepage's rounded field-and-button, so
 * the two pages read as one site rather than an older surface left behind.
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

async function postJson(path: string, body: Record<string, string>): Promise<Response> {
	return fetch(buildBackendUrl(path), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});
}

/**
 * The hero's inline variant: label goes to screen readers only, since the
 * placeholder plus the adjacent submit button already say what the field is
 * for at a glance -- a visible label here would just repeat "Email address"
 * next to a button reading "Email me a trial".
 */
function InlineEmailField({
	id,
	value,
	onChange,
}: {
	id: string;
	value: string;
	onChange: (value: string) => void;
}) {
	return (
		<>
			<label htmlFor={id} className="sr-only">
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
				className="min-w-0 flex-1 bg-transparent py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground"
			/>
		</>
	);
}

/**
 * Both forms' field and button as one pill, like the site's search pills, so
 * `/license` and `/downloads` cannot drift apart. The ring sits on the pill
 * because the field inside has no border of its own.
 */
function EmailPill({
	id,
	email,
	onEmailChange,
	busy,
	label,
	onSubmit,
}: {
	id: string;
	email: string;
	onEmailChange: (value: string) => void;
	busy: boolean;
	label: string;
	onSubmit: (event: React.FormEvent) => void;
}) {
	return (
		<form
			onSubmit={onSubmit}
			className="flex w-full max-w-md items-center gap-2 rounded-full border border-border bg-card py-1.5 pr-1.5 pl-5 shadow-xs focus-within:ring-3 focus-within:ring-ring/50"
		>
			<InlineEmailField id={id} value={email} onChange={onEmailChange} />
			<HomeButton
				type="submit"
				size="xl"
				disabled={busy}
				className="relative shrink-0 rounded-full px-5"
			>
				<span className={busy ? "opacity-0" : ""}>{label}</span>
				{busy ? <Spinner size="sm" className="absolute" /> : null}
			</HomeButton>
		</form>
	);
}

/**
 * The line under a pill: the outcome once there is one, the note until then.
 * A sent file points on to the activation steps, which the email also links.
 */
function PillMessage({ outcome, note }: { outcome: Outcome; note: string }) {
	if (!outcome && !note) return null;
	return (
		<p
			className={
				outcome?.kind === "error"
					? "max-w-sm text-sm text-destructive"
					: cn(siteText.body, "max-w-sm text-sm")
			}
		>
			{outcome ? outcome.message : note}
			{outcome?.kind === "ok" ? (
				<>
					{" "}
					<Link className={siteText.link} href="/license/activate">
						Activate it when it arrives
					</Link>
				</>
			) : null}
		</p>
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
			const response = await postJson("/api/v1/license/resend", { email: email.trim() });
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
		<div className="mt-10 flex flex-col items-center gap-5">
			<EmailPill
				id={`resend-email-${id}`}
				email={email}
				onEmailChange={setEmail}
				busy={busy}
				label="Send my license"
				onSubmit={handleSubmit}
			/>
			<PillMessage outcome={outcome} note="" />
		</div>
	);
}

const TRIAL_NOTE = "One trial per email address. We will send the license file to your inbox.";

export function TrialForm({
	label = "Email me a trial",
	note = TRIAL_NOTE,
}: {
	label?: string;
	note?: string;
} = {}) {
	const id = useId();
	const [email, setEmail] = useState("");
	const [busy, setBusy] = useState(false);
	const [outcome, setOutcome] = useState<Outcome>(null);

	async function handleSubmit(event: React.FormEvent) {
		event.preventDefault();
		if (busy || !email.trim()) return;

		setBusy(true);
		setOutcome(null);
		// A channel tag, never an id: the licence server counts issued trials by it.
		const channel = currentChannel();
		let status: number | null = null;
		try {
			const response = await postJson("/api/v1/license/trial", { email: email.trim(), channel });
			status = response.status;
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
			trackTrialRequested(trialOutcome(status), channel);
		}
	}

	return (
		<div className="mt-10 flex flex-col items-center gap-5">
			<EmailPill
				id={`trial-email-${id}`}
				email={email}
				onEmailChange={setEmail}
				busy={busy}
				label={label}
				onSubmit={handleSubmit}
			/>
			<PillMessage outcome={outcome} note={note} />
			{/* Always shown: someone whose trial or purchase email went missing lands here too. */}
			<p className={cn(siteText.body, "text-sm")}>
				Already have a license?{" "}
				<Link className={siteText.link} href="/license">
					Resend it
				</Link>
			</p>
		</div>
	);
}
