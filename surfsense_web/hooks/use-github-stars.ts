"use client";

import { useEffect, useState } from "react";

export const useGithubStars = () => {
	const [stars, setStars] = useState<number | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const abortController = new AbortController();
		const getStars = async () => {
			try {
				setError(null);

				const response = await fetch(`https://api.github.com/repos/MODSetter/SurfSense`, {
					signal: abortController.signal,
				});

				if (!response.ok) {
					throw new Error(`Failed to fetch stars: ${response.statusText}`);
				}

				const data = await response.json();

				setStars(data?.stargazers_count);
			} catch (err) {
				if (err instanceof Error) {
					console.error("Error fetching stars:", err);
					setError(err.message);
				}
			} finally {
				setLoading(false);
			}
		};

		getStars();

		return () => {
			abortController.abort();
		};
	}, []);

	return {
		stars,
		loading,
		error,
		compactFormat: Intl.NumberFormat("en-US", {
			notation: "compact",
			maximumFractionDigits: 1,
			minimumFractionDigits: 1,
		}).format(stars || 0),
	};
};
