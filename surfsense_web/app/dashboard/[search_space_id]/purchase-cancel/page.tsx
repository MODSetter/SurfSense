"use client";

import { CircleSlash2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

export default function PurchaseCancelPage() {
	const params = useParams();
	const searchSpaceId = String(params.search_space_id ?? "");

	return (
		<div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-8">
			<Card className="w-full max-w-lg">
				<CardHeader className="text-center">
					<CircleSlash2 className="mx-auto h-10 w-10 text-muted-foreground" />
					<CardTitle className="text-2xl">Checkout canceled</CardTitle>
					<CardDescription>
						No charge was made and your current pages are unchanged.
					</CardDescription>
				</CardHeader>
				<CardContent className="text-center text-sm text-muted-foreground">
					You can return to the pricing options and try again whenever you&apos;re ready.
				</CardContent>
				<CardFooter className="flex flex-col gap-2 sm:flex-row">
					<Button asChild className="w-full">
						<Link href={`/dashboard/${searchSpaceId}/more-pages`}>Back to Buy Pages</Link>
					</Button>
					<Button asChild variant="outline" className="w-full">
						<Link href={`/dashboard/${searchSpaceId}/new-chat`}>Back to Dashboard</Link>
					</Button>
				</CardFooter>
			</Card>
		</div>
	);
}
