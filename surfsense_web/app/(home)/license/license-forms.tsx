"use client";

import { useId, useState } from "react";
import { HomeButton } from "@/components/homepage/home/home-button";
import { ArrowRightIcon } from "@/components/ui/icons";
import { Spinner } from "@/components/ui/spinner";
import { buildBackendUrl } from "@/lib/env-config";

/**
 * The two forms on `/license` (`page.tsx`): the trial is folded straight into
 * the hero as the page's one primary action, styled after `/sunset`'s export
 * button; resending an existing license is secondary and stays collapsed
 * behind a plain disclosure link under it until asked for, reusing the same
 * `ss-home-faq` open/close mechanics as the FAQ lower on this page.
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
		<div className="flex flex-col items-center gap-2">
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
				className="w-100 max-w-full rounded-(--radius) border border-border bg-background px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
			/>
		</div>
	);
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
				className="w-64 rounded-(--radius) border border-border bg-background px-3 py-2.5 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
			/>
		</>
	);
}

/**
 * `ResendForm`'s wrapper, unlabelled and unboxed: it sits inside
 * `ResendDisclosure`'s own summary/heading, which already marks it off from
 * the hero above, so a border around the form too would be a second frame
 * around the same thing.
 */
function FormPanel({ description, children }: { description: string; children: React.ReactNode }) {
	return (
		<div className="flex flex-col items-center text-center">
			<p className="ss-home-body text-sm">{description}</p>
			<div className="mt-5 flex flex-col items-center">{children}</div>
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
			<form onSubmit={handleSubmit} className="flex flex-col items-center gap-4">
				<EmailField id={`resend-email-${id}`} value={email} onChange={setEmail} />
				<HomeButton type="submit" disabled={busy} variant="secondary">
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

/**
 * The hero's secondary action: a plain disclosure rather than a link to a
 * second page. Splitting resend onto its own route would buy nothing -- the
 * SEO brief already marks the whole page `noindex` -- while adding a click
 * for what is a rare action. Reuses `ss-home-faq`'s open/close mechanics (see
 * `home.css`) without its bordered summary row, since this sits centred in
 * the hero rather than in the FAQ's ruled grid.
 */
export function ResendDisclosure() {
	return (
		<details className="ss-home-faq group mx-auto mt-6 max-w-md">
			<summary className="ss-home-body flex cursor-pointer items-center justify-center gap-1.5 text-center text-sm [&::-webkit-details-marker]:hidden [&::marker]:hidden">
				<ArrowRightIcon
					aria-hidden="true"
					className="size-3.5 shrink-0 transition-transform duration-150 group-open:rotate-90"
				/>
				<span>
					Already licensed? <span className="ss-home-link">Get your license again</span>
				</span>
			</summary>
			<div className="mt-6">
				<ResendForm />
			</div>
		</details>
	);
}

const TRIAL_NOTE = "One trial per email address. We will send the license file to your inbox.";

export function TrialForm({ note = TRIAL_NOTE }: { note?: string } = {}) {
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
		<div className="mt-10 flex flex-col items-center gap-5">
			<form onSubmit={handleSubmit} className="flex items-center gap-2">
				<InlineEmailField id={`trial-email-${id}`} value={email} onChange={setEmail} />
				<HomeButton type="submit" size="xl" disabled={busy} className="relative shrink-0">
					<span className={busy ? "opacity-0" : ""}>Email me a trial</span>
					{busy ? <Spinner size="sm" className="absolute" /> : null}
				</HomeButton>
			</form>
			<p
				className={
					outcome?.kind === "error"
						? "max-w-sm text-sm text-destructive"
						: "ss-home-body max-w-sm text-sm"
				}
			>
				{outcome ? outcome.message : note}
			</p>
		</div>
	);
}
