"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { USER_QUERY_KEY } from "@/atoms/user/user-query.atoms";
import { authenticatedFetch } from "@/lib/auth-utils";
import { BACKEND_URL } from "@/lib/env-config";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

type VerifyState = "loading" | "verified" | "failed";

function SubscriptionSuccessContent() {
	const queryClient = useQueryClient();
	const searchParams = useSearchParams();
	const sessionId = searchParams.get("session_id");
	const [state, setState] = useState<VerifyState>("loading");
	const hasVerified = useRef(false);

	useEffect(() => {
		if (hasVerified.current) return;
		hasVerified.current = true;

		if (!sessionId) {
			setState("failed");
			return;
		}

		(async () => {
			try {
				const res = await authenticatedFetch(
					`${BACKEND_URL}/api/v1/stripe/verify-checkout-session?session_id=${encodeURIComponent(sessionId)}`
				);
				if (!res.ok) {
					setState("failed");
					return;
				}
				const data = await res.json();
				if (data.verified) {
					setState("verified");
					toast.success("Subscription activated! Welcome to Pro.");
					void queryClient.invalidateQueries({ queryKey: USER_QUERY_KEY });
				} else {
					setState("failed");
				}
			} catch {
				setState("failed");
			}
		})();
	}, [sessionId, queryClient]);

	if (state === "loading") {
		return (
			<div className="flex min-h-screen items-center justify-center px-4 py-8">
				<Card className="w-full max-w-lg">
					<CardHeader className="text-center">
						<Loader2 className="mx-auto h-10 w-10 animate-spin text-muted-foreground" />
						<CardTitle className="text-2xl">Verifying payment…</CardTitle>
					</CardHeader>
				</Card>
			</div>
		);
	}

	if (state === "failed") {
		return (
			<div className="flex min-h-screen items-center justify-center px-4 py-8">
				<Card className="w-full max-w-lg">
					<CardHeader className="text-center">
						<XCircle className="mx-auto h-10 w-10 text-destructive" />
						<CardTitle className="text-2xl">Verification failed</CardTitle>
						<CardDescription>
							We couldn&apos;t verify your payment. If you were charged, your subscription will activate shortly.
						</CardDescription>
					</CardHeader>
					<CardFooter className="flex justify-center gap-3">
						<Button asChild>
							<Link href="/dashboard">Go to Dashboard</Link>
						</Button>
						<Button variant="outline" asChild>
							<Link href="/pricing">View Plans</Link>
						</Button>
					</CardFooter>
				</Card>
			</div>
		);
	}

	return (
		<div className="flex min-h-screen items-center justify-center px-4 py-8">
			<Card className="w-full max-w-lg">
				<CardHeader className="text-center">
					<CheckCircle2 className="mx-auto h-10 w-10 text-emerald-500" />
					<CardTitle className="text-2xl">Subscription activated!</CardTitle>
					<CardDescription>
						Your Pro plan is now active. Enjoy unlimited power.
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3 text-center">
					<p className="text-sm text-muted-foreground">
						Your account has been upgraded. All Pro features are now available.
					</p>
				</CardContent>
				<CardFooter className="flex justify-center gap-3">
					<Button asChild>
						<Link href="/dashboard">Go to Dashboard</Link>
					</Button>
					<Button variant="outline" asChild>
						<Link href="/pricing">View Plans</Link>
					</Button>
				</CardFooter>
			</Card>
		</div>
	);
}

export default function SubscriptionSuccessPage() {
	return (
		<Suspense>
			<SubscriptionSuccessContent />
		</Suspense>
	);
}
