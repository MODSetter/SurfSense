import { ImageModelManager } from "@/components/settings/image-model-manager";

export default async function Page({
	params,
}: {
	params: Promise<{ search_space_id: string }>;
}) {
	const { search_space_id } = await params;
	return <ImageModelManager searchSpaceId={Number(search_space_id)} />;
}
