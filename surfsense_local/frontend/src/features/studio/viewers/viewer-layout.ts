// The stage in ArtifactPanel has no padding of its own, so a canvas viewer
// (mindmap, xlsx's table) can sit flush against the panel edges. A viewer
// that renders flowing content instead — text, a card, a centered message —
// applies this to its own root so that content doesn't touch the edges.
export const VIEWER_PADDING = "px-5 py-4"
