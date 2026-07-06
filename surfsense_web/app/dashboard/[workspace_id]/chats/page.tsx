import { AllChatsWorkspaceContent } from "@/components/layout/ui/sidebar";

export default async function ChatsPage({ params }: { params: Promise<{ workspace_id: string }> }) {
	const { workspace_id } = await params;

	return (
		<div className="w-full select-none">
			<AllChatsWorkspaceContent searchSpaceId={workspace_id} />
		</div>
	);
}
