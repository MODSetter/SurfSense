import { PublicChatView } from "@/components/public-chat/public-chat-view";

export default async function PublicChatPage({ params }: { params: Promise<{ token: string }> }) {
	const { token } = await params;

	return <PublicChatView shareToken={token} />;
}
