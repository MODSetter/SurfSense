import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api";

export const useGithubStarts = () => {
	const repo = process.env.NEXT_PUBLIC_GITHUB_REPO;
	const owner = process.env.NEXT_PUBLIC_GITHUB_OWNER;
	const token = process.env.NEXT_PUBLIC_GITHUB_TOKEN;

	const [starts, setStarts] = useState<number | null>(null);

	useEffect(() => {
		const getStarts = async () => {
			try {
				if (!repo || !owner || !token) {
					throw new Error("Missing GitHub credentials");
				}
				const response = await apiClient.get<{ stargazers_count: number }>(
					`https://api.github.com/repos/${owner}/${repo}`,
					{
						headers: {
							Authorization: `Bearer ${token}`,
						},
					}
				);

				setStarts(response.stargazers_count);
			} catch (err) {
				console.error("Error fetching starts:", err);
				throw err;
			}
		};

		getStarts();
	}, []);

	return { starts };
};
