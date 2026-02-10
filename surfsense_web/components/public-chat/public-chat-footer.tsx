"use client";

import { Copy } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { publicChatApiService } from "@/lib/apis/public-chat-api.service";
import { getBearerToken } from "@/lib/auth-utils";

interface PublicChatFooterProps {
	shareToken: string;
}

export function PublicChatFooter({ shareToken }: PublicChatFooterProps) {
	const router = useRouter();
	const searchParams = useSearchParams();
	const [isCloning, setIsCloning] = useState(false);
	const hasAutoCloned = useRef(false);

	const triggerClone = useCallback(async () => {
		setIsCloning(true);

		try {
			const response = await publicChatApiService.clonePublicChat({
				share_token: shareToken,
			});

			// Redirect to the new chat page with cloned content
			router.push(`/dashboard/${response.search_space_id}/new-chat/${response.thread_id}`);
		} catch (error) {
			const message = error instanceof Error ? error.message : "Failed to copy chat";
			toast.error(message);
			setIsCloning(false);
		}
	}, [shareToken, router]);

	// Auto-trigger clone if user just logged in with action=clone
	useEffect(() => {
		const action = searchParams.get("action");
		const token = getBearerToken();

		// Only auto-clone once, if authenticated and action=clone is present
		if (action === "clone" && token && !hasAutoCloned.current && !isCloning) {
			hasAutoCloned.current = true;
			triggerClone();
		}
	}, [searchParams, isCloning, triggerClone]);

	const handleCopyAndContinue = async () => {
		const token = getBearerToken();

		if (!token) {
			// Include action=clone in the returnUrl so it persists after login
			const returnUrl = encodeURIComponent(`/public/${shareToken}?action=clone`);
			router.push(`/login?returnUrl=${returnUrl}`);
			return;
		}

		await triggerClone();
	};

	return (
		<div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2">
			<Button
				size="lg"
				onClick={handleCopyAndContinue}
				disabled={isCloning}
				className="gap-2 rounded-full px-6 shadow-lg transition-all duration-200 hover:scale-[1.02] hover:shadow-xl hover:brightness-110 hover:bg-primary"
			>
				{isCloning ? <Spinner size="sm" /> : <Copy className="size-4" />}
				Copy and continue this chat
			</Button>
		</div>
	);
}
