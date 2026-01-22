import { useQuery } from "@tanstack/react-query";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface UseComposioDriveFoldersOptions {
	connectorId: number;
	parentId?: string;
	enabled?: boolean;
}

export function useComposioDriveFolders({
	connectorId,
	parentId,
	enabled = true,
}: UseComposioDriveFoldersOptions) {
	return useQuery({
		queryKey: cacheKeys.connectors.composioDrive.folders(connectorId, parentId),
		queryFn: async () => {
			return connectorsApiService.listComposioDriveFolders({
				connector_id: connectorId,
				parent_id: parentId,
			});
		},
		enabled: enabled && !!connectorId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		retry: 2,
	});
}
