import { useQuery } from "@tanstack/react-query";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface UseGoogleDriveFoldersOptions {
	connectorId: number;
	parentId?: string;
	enabled?: boolean;
}

export function useGoogleDriveFolders({
	connectorId,
	parentId,
	enabled = true,
}: UseGoogleDriveFoldersOptions) {
	return useQuery({
		queryKey: cacheKeys.connectors.googleDrive.folders(connectorId, parentId),
		queryFn: async () => {
			return connectorsApiService.listGoogleDriveFolders({
				connector_id: connectorId,
				parent_id: parentId,
			});
		},
		enabled: enabled && !!connectorId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		retry: 2,
	});
}
