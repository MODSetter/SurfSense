/**
 * The body as UTF-8 text, or null as soon as it passes `limitBytes`. Stops
 * reading there, so an oversized or endless body costs no more than the limit.
 * Throws on invalid UTF-8.
 */
export async function readTextWithin(request: Request, limitBytes: number): Promise<string | null> {
	const declared = Number(request.headers.get("content-length"));
	if (Number.isFinite(declared) && declared > limitBytes) return null;
	if (!request.body) return "";

	const reader = request.body.getReader();
	const chunks: Uint8Array[] = [];
	let size = 0;
	for (;;) {
		const { done, value } = await reader.read();
		if (done) break;
		size += value.byteLength;
		if (size > limitBytes) {
			await reader.cancel();
			return null;
		}
		chunks.push(value);
	}
	return new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks));
}
