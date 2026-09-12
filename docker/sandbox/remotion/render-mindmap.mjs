import {readFile, mkdir, rename, rm, stat} from "node:fs/promises";
import path from "node:path";
import {fileURLToPath, pathToFileURL} from "node:url";
import {
  makeCancelSignal,
  renderStill,
  selectComposition,
} from "@remotion/renderer";

const rootDir = path.dirname(fileURLToPath(import.meta.url));
const defaultBundle = path.join(rootDir, "bundle");
const renderTimeout = Number(
  process.env.MINDMAP_RENDER_TIMEOUT_MS ?? 20_000,
);
const MAX_NODES = 60;
const MAX_DEPTH = 6;
const MAX_LABEL_LENGTH = 120;
const UNSUPPORTED_MARKDOWN =
  /(^|\s)(?:```|~~~|:::)|(^|\n)\s*(?:>|\|.*\|\s*$)|!\[|\[[^\]\n]+\](?:\(|\[)|<[^>\n]+>/m;

export class MindmapRenderError extends Error {
  constructor(code, error) {
    super(error instanceof Error ? error.message : String(error), {cause: error});
    this.name = "MindmapRenderError";
    this.code = code;
  }
}

function stageError(code, error) {
  return error instanceof MindmapRenderError
    ? error
    : new MindmapRenderError(code, error);
}

export function validateMindmapMarkdown(markdown) {
  if (!markdown.trim()) throw new Error("Mind-map Markdown must not be empty");
  for (let index = 0; index < markdown.length; index += 1) {
    const code = markdown.charCodeAt(index);
    if (
      code <= 8 ||
      code === 11 ||
      code === 12 ||
      (code >= 14 && code <= 31) ||
      code === 127
    ) {
      throw new Error("Mind-map Markdown contains control characters");
    }
  }
  if (UNSUPPORTED_MARKDOWN.test(markdown)) {
    throw new Error("Mind-map Markdown contains an unsupported construct");
  }

  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const headings = lines.filter((line) => /^#{1,6}\s+/.test(line));
  if (headings.length !== 1 || !/^#\s+\S/.test(headings[0])) {
    throw new Error("Mind map must have exactly one non-empty level-one heading");
  }
  if (lines.find((line) => line.trim()) !== headings[0]) {
    throw new Error("Mind-map root heading must be the first content");
  }

  let nodes = 1;
  let indentWidth;
  let previousLevel = 0;
  let sawChild = false;
  for (const line of lines) {
    if (!line.trim() || line === headings[0]) continue;
    const match = /^( *)(?:[-+*])\s+(.+)$/.exec(line);
    if (!match) {
      throw new Error("Mind map may contain only one root heading and list nodes");
    }
    const indent = match[1].length;
    if (!sawChild && indent) {
      throw new Error("Mind-map first list node must start at the first level");
    }
    if (indent) {
      if (indentWidth === undefined) {
        indentWidth = indent;
        if (indentWidth < 2 || indentWidth > 4) {
          throw new Error("Mind-map indentation must use 2-4 spaces per level");
        }
      }
      if (indent % indentWidth !== 0) {
        throw new Error("Mind-map list indentation is inconsistent");
      }
    }
    const level = indentWidth === undefined ? 0 : indent / indentWidth;
    if (level > previousLevel + 1) {
      throw new Error("Mind-map hierarchy skips a nesting level");
    }
    const depth = level + 2;
    if (depth > MAX_DEPTH) {
      throw new Error(`Mind map exceeds maximum depth ${MAX_DEPTH}`);
    }
    const label = match[2].trim();
    if (!label) throw new Error("Mind-map node labels must not be empty");
    if (label.length > MAX_LABEL_LENGTH) {
      throw new Error(
        `Mind-map node label exceeds ${MAX_LABEL_LENGTH} characters`,
      );
    }
    nodes += 1;
    if (nodes > MAX_NODES) {
      throw new Error(`Mind map exceeds maximum node count ${MAX_NODES}`);
    }
    previousLevel = level;
    sawChild = true;
  }
  if (!sawChild) throw new Error("Mind map must contain at least one child node");
  return {nodes};
}

export function parseArguments(argv) {
  if (argv.length !== 2) {
    throw new Error(
      "Usage: node /opt/remotion/render-mindmap.mjs input.md output.png",
    );
  }
  const markdownPath = path.resolve(argv[0]);
  const outputPath = path.resolve(argv[1]);
  if (path.extname(outputPath).toLowerCase() !== ".png") {
    throw new Error("Output path must end in .png");
  }
  return {markdownPath, outputPath};
}

export async function renderMindmap(
  argv = process.argv.slice(2),
  {
    serveUrl = process.env.REMOTION_BUNDLE_PATH ?? defaultBundle,
    browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || undefined,
    select = selectComposition,
    render = renderStill,
  } = {},
) {
  if (!Number.isFinite(renderTimeout) || renderTimeout < 1_000) {
    throw new MindmapRenderError(
      "argument_validation",
      new Error("MINDMAP_RENDER_TIMEOUT_MS must be at least 1000"),
    );
  }
  let markdownPath;
  let outputPath;
  try {
    ({markdownPath, outputPath} = parseArguments(argv));
  } catch (error) {
    throw stageError("argument_validation", error);
  }
  let markdown;
  try {
    markdown = new TextDecoder("utf-8", {fatal: true}).decode(
      await readFile(markdownPath),
    );
    validateMindmapMarkdown(markdown);
  } catch (error) {
    throw stageError("markdown_transform", error);
  }

  let composition;
  try {
    await stat(serveUrl);
    composition = await select({
      serveUrl,
      id: "Mindmap",
      inputProps: {markdown},
      browserExecutable,
    });
  } catch (error) {
    throw stageError("layout_readiness", error);
  }
  if (composition.width !== 2400 || composition.height !== 1600) {
    throw new MindmapRenderError(
      "layout_readiness",
      new Error("Mind-map composition must be exactly 2400x1600"),
    );
  }

  await mkdir(path.dirname(outputPath), {recursive: true});
  const stagedOutput = path.join(
    path.dirname(outputPath),
    `.${path.basename(outputPath)}.${process.pid}.${Date.now()}.tmp.png`,
  );
  const {cancelSignal, cancel} = makeCancelSignal();
  const requestCancel = () => cancel();
  process.once("SIGINT", requestCancel);
  process.once("SIGTERM", requestCancel);
  try {
    await render({
      composition,
      serveUrl,
      output: stagedOutput,
      frame: 0,
      imageFormat: "png",
      inputProps: {markdown},
      overwrite: true,
      chromiumOptions: {enableMultiProcessOnLinux: true},
      timeoutInMilliseconds: renderTimeout,
      cancelSignal,
      browserExecutable,
    });
  } catch (error) {
    await rm(stagedOutput, {force: true});
    const timedOut = /tim(?:ed? out|eout)/i.test(
      error instanceof Error ? error.message : String(error),
    );
    throw stageError(timedOut ? "render_timeout" : "layout_readiness", error);
  } finally {
    process.off("SIGINT", requestCancel);
    process.off("SIGTERM", requestCancel);
  }

  try {
    const output = await stat(stagedOutput);
    if (!output.isFile() || output.size === 0) {
      throw new Error("Mind-map renderer produced no PNG data");
    }
    await rename(stagedOutput, outputPath);
  } catch (error) {
    await rm(stagedOutput, {force: true});
    throw stageError("output_publication", error);
  }

  const result = {
    ok: true,
    output: outputPath,
    width: composition.width,
    height: composition.height,
  };
  console.log(JSON.stringify(result));
  return result;
}

const invokedPath = process.argv[1]
  ? pathToFileURL(path.resolve(process.argv[1])).href
  : undefined;
if (invokedPath === import.meta.url) {
  renderMindmap().catch((error) => {
    console.error(
      JSON.stringify({
        ok: false,
        code:
          error instanceof MindmapRenderError
            ? error.code
            : "mindmap_render_error",
        message: error instanceof Error ? error.message : String(error),
      }),
    );
    process.exitCode = 1;
  });
}
