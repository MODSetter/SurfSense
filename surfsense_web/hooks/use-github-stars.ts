import { useEffect, useState } from "react";

export const useGithubStars = () => {
	const repo = process.env.NEXT_PUBLIC_GITHUB_REPO;
	const owner = process.env.NEXT_PUBLIC_GITHUB_OWNER;

	const [stars, setStars] = useState<number | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const getStars = async () => {
			try {
				if (!repo || !owner) {
					throw new Error("Missing GitHub credentials");
				}

				setError(null);

				const response = await fetch(`https://api.github.com/repos/${owner}/${repo}`);

				if (!response.ok) {
					throw new Error(`Failed to fetch stars: ${response.statusText}`);
				}

				const data = await response.json();

				setStars(data?.stargazers_count);
			} catch (err) {
				console.error("Error fetching stars:", err);
				setError(err instanceof Error ? err.message : `Failed to fetch stars ${err}`);
				throw err;
			} finally {
				setLoading(false);
			}
		};

		getStars();
	}, []);

	return {
		stars,
		loading,
		error,
		compactFormat: Intl.NumberFormat("en-US", {
			notation: "compact",
		}).format(stars || 0),
	};
};
