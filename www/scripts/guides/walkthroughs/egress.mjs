/** Settings › Network's destinations, switched through the API outside any recording. */

/** Allows or blocks every destination on `host`, so a take starts as the first take did. */
export async function setHostAllowed(apiUrl, host, enabled) {
	const destinations = await (await fetch(`${apiUrl}/egress`)).json();
	const changing = destinations.filter((each) => each.host === host && each.enabled !== enabled);
	if (!changing.length) return;
	await fetch(`${apiUrl}/egress`, {
		method: "PUT",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			destinations: changing.map((each) => each.destination),
			enabled,
		}),
	});
}
