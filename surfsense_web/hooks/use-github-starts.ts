import { useCallback, useEffect, useState } from "react";

export const useGithubStarts = () => {
	const repo = process.env.NEXT_PUBLIC_GITHUB_REPO;
	const owner = process.env.NEXT_PUBLIC_GITHUB_OWNER;

	const [starts, setStarts] = useState<number | null>(null);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		const getStarts = async () => {
			try {
				if (!repo || !owner) {
					throw new Error("Missing GitHub credentials");
				}

				const response = await fetch(`https://api.github.com/repos/${owner}/${repo}`);

				if (!response.ok) {
					throw new Error(`Failed to fetch starts: ${response.statusText}`);
				}

				const data = await response.json();

				setStarts(data?.stargazers_count);
			} catch (err) {
				console.error("Error fetching starts:", err);
				throw err;
			} finally {
				setLoading(false);
			}
		};

		getStarts();
	}, []);

	return {
		starts,
		loading,
		compactFormat: Intl.NumberFormat("en-US", {
			notation: "compact",
		}).format(starts || 0),
	};
};
