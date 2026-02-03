"use client";

import { Link2Off } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Navbar } from "@/components/homepage/navbar";

export function PublicChatNotFound() {
	const t = useTranslations("public_chat");

	return (
		<main className="min-h-screen bg-linear-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white overflow-x-hidden">
			<Navbar />
			<div className="flex h-screen flex-col items-center justify-center gap-6 px-4 text-center">
				<div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
					<Link2Off className="h-8 w-8 text-muted-foreground" />
				</div>
				<div className="flex flex-col gap-2">
					<h1 className="text-2xl font-semibold">{t("not_found_title")}</h1>
					<p className="text-muted-foreground">
						<Link href="/login" className="text-primary underline hover:text-primary/80">
							{t("click_here")}
						</Link>{" "}
						{t("sign_in_prompt")}
					</p>
				</div>
			</div>
		</main>
	);
}
