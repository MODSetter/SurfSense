import { VisionModelManager } from "@/components/settings/vision-model-manager";

export default async function Page({ params }: { params: Promise<{ search_space_id: string }> }) {
	const { search_space_id } = await params;
	return <VisionModelManager searchSpaceId={Number(search_space_id)} />;
}
