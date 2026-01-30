"use client";

import { Copy, Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
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
		<div className="mx-auto flex max-w-(--thread-max-width) items-center justify-center px-4 py-4">
			<Button size="lg" onClick={handleCopyAndContinue} disabled={isCloning} className="gap-2">
				{isCloning ? <Loader2 className="size-4 animate-spin" /> : <Copy className="size-4" />}
				Copy and continue this chat
			</Button>
		</div>
	);
}
