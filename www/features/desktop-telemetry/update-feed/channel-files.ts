// The four 2.x channel files. latest*.yml belongs to the legacy 0.0.x bridge
// on GitHub and must never be served from here.
const CHANNEL_FILE = /^stable(-mac|-linux(-arm64)?)?\.yml$/;

export function isChannelFile(file: string): boolean {
	return CHANNEL_FILE.test(file);
}
