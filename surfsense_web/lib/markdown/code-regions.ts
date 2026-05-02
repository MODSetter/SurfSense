// Matches fenced (```...```) and inline (`...`) code regions. Used by MDX
// escaping and citation preprocessing — single source of truth so future
// edits stay in sync.
//
// String.split() with this capturing pattern places non-code parts at even
// indexes and matched code regions at odd indexes — preserve odd-indexed
// segments verbatim when transforming markdown.
export const FENCED_OR_INLINE_CODE = /(```[\s\S]*?```|`[^`\n]+`)/g;
