import { ServerBlockNoteEditor } from "@blocknote/server-util";
import { type NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
	try {
		const { blocknote_document } = await request.json();

		if (!blocknote_document || !Array.isArray(blocknote_document)) {
			return NextResponse.json({ error: "BlockNote document array is required" }, { status: 400 });
		}

		// Create server-side editor instance
		const editor = ServerBlockNoteEditor.create();

		// Convert BlockNote blocks to markdown
		const markdown = await editor.blocksToMarkdownLossy(blocknote_document);

		return NextResponse.json({
			markdown,
		});
	} catch (error) {
		console.error("Failed to convert BlockNote to markdown:", error);
		return NextResponse.json(
			{ error: "Failed to convert BlockNote blocks to markdown" },
			{ status: 500 }
		);
	}
}
