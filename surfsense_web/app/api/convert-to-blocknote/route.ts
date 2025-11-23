import { ServerBlockNoteEditor } from "@blocknote/server-util";
import { type NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
	try {
		const { markdown } = await request.json();

		if (!markdown || typeof markdown !== "string") {
			return NextResponse.json({ error: "Markdown string is required" }, { status: 400 });
		}

		// Log raw markdown input before conversion
		// console.log(`\n${"=".repeat(80)}`);
		// console.log("RAW MARKDOWN INPUT (BEFORE CONVERSION):");
		// console.log("=".repeat(80));
		// console.log(markdown);
		// console.log(`${"=".repeat(80)}\n`);

		// Create server-side editor instance
		const editor = ServerBlockNoteEditor.create();

		// Convert markdown directly to BlockNote blocks
		const blocks = await editor.tryParseMarkdownToBlocks(markdown);

		if (!blocks || blocks.length === 0) {
			throw new Error("Markdown parsing returned no blocks");
		}

		return NextResponse.json({ blocknote_document: blocks });
	} catch (error: any) {
		console.error("Failed to convert markdown to BlockNote:", error);
		return NextResponse.json(
			{
				error: "Failed to convert markdown to BlockNote blocks",
				details: error.message,
			},
			{ status: 500 }
		);
	}
}
