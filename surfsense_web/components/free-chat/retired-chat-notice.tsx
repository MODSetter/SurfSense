import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

/**
 * Replaces the anonymous chat box on `/free/{slug}` now that chatting without
 * an account is retired.
 *
 * The pages themselves stay: they rank, and they bring roughly 19,600 visitors
 * a month. So this has to read as "here is how to use this model" rather than
 * as an error page — a visitor who searched for the model still gets an answer
 * to what they came for, just one that requires an account.
 */
export function RetiredChatNotice({ modelName }: { modelName: string }) {
	return (
		<section className="mx-auto flex max-w-xl flex-col items-center gap-5 px-6 py-16 text-center">
			<h2 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
				{modelName} now needs a free account
			</h2>
			<p className="text-pretty text-sm leading-relaxed text-muted-foreground">
				Chatting without signing up has been retired. Creating an account is free and takes a
				moment, and it comes with a monthly allowance you can spend on {modelName} or any other
				model.
			</p>
			<div className="flex flex-col gap-3 sm:flex-row">
				<Button asChild size="lg">
					<Link href="/register">
						Create free account
						<ArrowRight className="size-4" />
					</Link>
				</Button>
				<Button asChild size="lg" variant="outline">
					<Link href="/login">Log in</Link>
				</Button>
			</div>
			<p className="text-xs text-muted-foreground">
				An account also unlocks document Q&amp;A, connectors, and team workspaces.
			</p>
		</section>
	);
}
