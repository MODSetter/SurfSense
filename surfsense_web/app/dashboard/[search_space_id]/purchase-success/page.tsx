"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { USER_QUERY_KEY } from "@/atoms/user/user-query.atoms";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

export default function PurchaseSuccessPage() {
	const params = useParams();
	const queryClient = useQueryClient();
	const searchSpaceId = String(params.search_space_id ?? "");

	useEffect(() => {
		void queryClient.invalidateQueries({ queryKey: USER_QUERY_KEY });
		void queryClient.invalidateQueries({ queryKey: ["token-status"] });
	}, [queryClient]);

	return (
		<div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-8">
			<Card className="w-full max-w-lg">
				<CardHeader className="text-center">
					<CheckCircle2 className="mx-auto h-10 w-10 text-emerald-500" />
					<CardTitle className="text-2xl">Purchase complete</CardTitle>
					<CardDescription>Your purchase is being applied to your account now.</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3 text-center">
					<p className="text-sm text-muted-foreground">
						Your usage meters should refresh automatically in a moment.
					</p>
				</CardContent>
				<CardFooter className="flex flex-col gap-2">
					<Button asChild className="w-full">
						<Link href={`/dashboard/${searchSpaceId}/new-chat`}>Back to Dashboard</Link>
					</Button>
					<Button asChild variant="outline" className="w-full">
						<Link href={`/dashboard/${searchSpaceId}/buy-more`}>Buy More</Link>
					</Button>
				</CardFooter>
			</Card>
		</div>
	);
}
