"use client";

import { useParams } from "next/navigation";
import { PublicChatView } from "@/components/public-chat/public-chat-view";

export default function PublicChatPage() {
	const params = useParams();
	const token = params.token as string;

	return <PublicChatView shareToken={token} />;
}
