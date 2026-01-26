"use client";

import { Copy, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { publicChatApiService } from "@/lib/apis/public-chat-api.service";
import { getBearerToken } from "@/lib/auth-utils";

interface PublicChatFooterProps {
	shareToken: string;
}

export function PublicChatFooter({ shareToken }: PublicChatFooterProps) {
	const router = useRouter();
	const [isCloning, setIsCloning] = useState(false);

	const handleCopyAndContinue = async () => {
		const token = getBearerToken();

		if (!token) {
			const returnUrl = encodeURIComponent(`/public/${shareToken}`);
			router.push(`/login?returnUrl=${returnUrl}&action=clone`);
			return;
		}

		setIsCloning(true);

		try {
			await publicChatApiService.clonePublicChat({
				share_token: shareToken,
			});

			toast.success("Copying chat to your account...", {
				description: "You'll be notified when it's ready.",
			});

			router.push("/dashboard");
		} catch (error) {
			const message = error instanceof Error ? error.message : "Failed to copy chat";
			toast.error(message);
		} finally {
			setIsCloning(false);
		}
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
