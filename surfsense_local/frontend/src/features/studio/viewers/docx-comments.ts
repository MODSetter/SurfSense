/**
 * A Word file's comments beside its pages, as Word shows them: each commented
 * passage shaded and numbered, its comment in a balloon in the margin at the
 * passage's height. docx-preview alone hides each comment in a popover behind
 * a hover on a small icon, where a revised copy's reader never finds it.
 */

import type { Options } from "docx-preview"

import { intl } from "@/i18n/intl"

// docx-preview's class prefix, its default.
const PREFIX = "docx"
const BALLOON_WIDTH = 208
// Between a page and its balloons, and between two balloons.
const PAGE_GAP = 16
const BALLOON_GAP = 8
/** The room the balloons take to the right of the pages. */
export const COMMENT_GUTTER = BALLOON_WIDTH + PAGE_GAP + 8

// Fixed colours: the pages are always white.
const COMMENTS_CSS = `
.surfsense-comment-anchor { background: #fef3c7; }
.surfsense-comment-ref {
  display: inline-block; min-width: 1.5em; margin: 0 0.15em; padding: 0 0.3em;
  border-radius: 0.75em; background: #d97706; color: #ffffff;
  font: 600 0.65em/1.5 Arial, sans-serif; text-align: center; vertical-align: super;
}
.surfsense-comment {
  position: absolute; width: ${BALLOON_WIDTH}px; box-sizing: border-box; padding: 6px 8px;
  background: #fffbeb; border: 1px solid #fcd34d; border-left: 3px solid #d97706;
  border-radius: 4px; color: #1f2937; font: 12px/1.45 Arial, sans-serif;
}
.surfsense-comment-head { display: flex; flex-wrap: wrap; gap: 0 6px; margin-bottom: 2px; color: #6b7280; }
.surfsense-comment-head b { color: #92400e; }
.surfsense-comment p { margin: 0; }
`

type Made = Parameters<Options["h"]>[0]

/** An element with no child missing: a comment saved without an author has a null one, which the maker throws on. */
function filled(element: Made): Made {
  if (typeof element !== "object" || element instanceof Node) return element
  return {
    ...element,
    children: element.children?.map((child) =>
      child == null ? "" : filled(child)
    ),
  }
}

/**
 * docx-preview's element maker, mended for comments: 0.4.0 makes a comment's
 * reference and its text as a fragment, then drops the fragment's children,
 * so neither reaches the page; and it throws on a comment with no author.
 */
export function mendedMaker(make: Options["h"]): Options["h"] {
  const h: Options["h"] = (element) => {
    if (
      typeof element === "object" &&
      !(element instanceof Node) &&
      element.tagName === "#fragment"
    ) {
      const fragment = document.createDocumentFragment()
      for (const child of element.children ?? []) {
        fragment.append(h(child == null ? "" : child))
      }
      return fragment
    }
    return make(filled(element))
  }
  return h
}

type Note = {
  number: string
  anchor: HTMLElement
  balloon: HTMLElement
}

/**
 * The comment a reference points to, from what docx-preview writes before it:
 * `comment #ID by AUTHOR on DATE`. Its own date line reads 1970 for a comment
 * saved without one, so the date comes from here.
 */
function referenced(
  ref: HTMLElement
): { id: string; date: Date | null } | null {
  const before = ref.previousSibling
  if (before?.nodeType !== Node.COMMENT_NODE) return null
  const found = /^comment #(\S+) by [\s\S]* on ([^ ]*)$/.exec(
    before.nodeValue ?? ""
  )
  if (!found) return null
  return { id: found[1], date: wordTime(found[2]) }
}

/**
 * A comment's time as Word shows it. Word writes its own clock's time with a
 * Z after it, and shows it back unconverted; read as UTC, it would move by
 * the reader's offset.
 */
function wordTime(written: string): Date | null {
  const parts = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/.exec(written)
  if (!parts) return null
  const [year, month, day, hour, minute] = parts
    .slice(1)
    .map((part) => Number(part ?? 0))
  const time = new Date(year, month - 1, day, hour, minute)
  return Number.isNaN(time.getTime()) ? null : time
}

/** Shade the text between each comment's start and end, which docx-preview marks with HTML comments. */
function shadePassages(
  container: HTMLElement,
  numbers: Map<string, string>
): Map<string, HTMLElement> {
  const pages = container.ownerDocument
  const bounds = new Map<string, { start?: Node; end?: Node }>()
  const walker = pages.createTreeWalker(container, NodeFilter.SHOW_COMMENT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const found = /^(start|end) of comment #(\S+)$/.exec(node.nodeValue ?? "")
    if (!found) continue
    const [, which, id] = found
    const bound = bounds.get(id) ?? {}
    bound[which as "start" | "end"] = node
    bounds.set(id, bound)
  }
  const firsts = new Map<string, HTMLElement>()
  for (const [id, { start, end }] of bounds) {
    const number = numbers.get(id)
    if (!number || !start || !end) continue
    const range = pages.createRange()
    range.setStartAfter(start)
    range.setEndBefore(end)
    const texts: Text[] = []
    const inside = pages.createTreeWalker(
      range.commonAncestorContainer,
      NodeFilter.SHOW_TEXT
    )
    for (let text = inside.nextNode(); text; text = inside.nextNode()) {
      // A reply's passage holds its parent's marker, which stays unshaded.
      if (
        text.nodeValue &&
        range.intersectsNode(text) &&
        !text.parentElement?.closest(".surfsense-comment-ref")
      ) {
        texts.push(text as Text)
      }
    }
    for (const text of texts) {
      // Text two comments cover gets one shade naming both, not one in another.
      const parent = text.parentElement
      let shade: HTMLElement
      if (parent?.classList.contains("surfsense-comment-anchor")) {
        shade = parent
        shade.dataset.notes = `${shade.dataset.notes} ${number}`
      } else {
        shade = pages.createElement("span")
        shade.className = "surfsense-comment-anchor"
        shade.dataset.notes = number
        text.replaceWith(shade)
        shade.append(text)
      }
      if (!firsts.has(id)) firsts.set(id, shade)
    }
  }
  return firsts
}

/** Where an element sits below the top of `ancestor`, in the pages' own pixels. */
function offsetWithin(element: HTMLElement, ancestor: HTMLElement): number {
  let top = 0
  let node: HTMLElement | null = element
  while (node && node !== ancestor) {
    top += node.offsetTop
    node = node.offsetParent as HTMLElement | null
  }
  return top
}

/**
 * Move each comment docx-preview laid out into a balloon beside the pages,
 * before the pages go into the frame. Returns what places the balloons, to
 * call once the pages are laid out, and again when their fonts load; null
 * when the file has no comments.
 */
export function gatherComments(container: HTMLElement): (() => void) | null {
  const pages = container.ownerDocument
  const wrapper = container.querySelector<HTMLElement>(`.${PREFIX}-wrapper`)
  const refs = [
    ...container.querySelectorAll<HTMLElement>(`.${PREFIX}-comment-ref`),
  ]
  if (!wrapper || refs.length === 0) return null

  const numbers = new Map<string, string>()
  const notes: Omit<Note, "anchor">[] = []
  const refsById = new Map<string, HTMLElement>()
  for (const ref of refs) {
    const popover = ref.nextElementSibling
    if (!popover?.classList.contains(`${PREFIX}-comment-popover`)) continue
    const number = String(notes.length + 1)
    const comment = referenced(ref)
    const id = comment?.id ?? null
    if (id !== null) {
      numbers.set(id, number)
      refsById.set(id, ref)
    }
    ref.textContent = number
    ref.className = "surfsense-comment-ref"
    ref.dataset.note = number

    const [author, , ...body] = [...popover.children]
    const balloon = pages.createElement("aside")
    balloon.className = "surfsense-comment"
    balloon.dataset.note = number
    const head = pages.createElement("div")
    head.className = "surfsense-comment-head"
    const label = pages.createElement("b")
    label.textContent = number
    const who = pages.createElement("span")
    who.textContent = author?.textContent ?? ""
    head.append(label, who)
    if (comment?.date) {
      const when = pages.createElement("span")
      when.textContent = intl.formatDate(comment.date, {
        dateStyle: "medium",
        timeStyle: "short",
      })
      head.append(when)
    }
    balloon.append(head, ...body)
    popover.remove()
    wrapper.append(balloon)
    notes.push({ number, balloon })
  }
  if (notes.length === 0) return null

  const firsts = shadePassages(container, numbers)
  const anchors = new Map<string, HTMLElement>()
  for (const [id, number] of numbers) {
    anchors.set(number, firsts.get(id) ?? refsById.get(id)!)
  }
  const placed: Note[] = notes.map((note) => ({
    ...note,
    anchor:
      anchors.get(note.number) ??
      container.querySelector<HTMLElement>(
        `.surfsense-comment-ref[data-note="${note.number}"]`
      )!,
  }))

  // Hovering a balloon deepens its passage's shade.
  const style = pages.createElement("style")
  style.textContent =
    COMMENTS_CSS +
    placed
      .map(
        ({ number }) =>
          `.${PREFIX}-wrapper:has(.surfsense-comment[data-note="${number}"]:hover) ` +
          `.surfsense-comment-anchor[data-notes~="${number}"] { background: #fcd34d; }`
      )
      .join("\n")
  container.append(style)
  // The pages stay centred in what is left of the frame beside the balloons.
  wrapper.style.position = "relative"
  wrapper.style.paddingRight = `${30 + COMMENT_GUTTER}px`

  return () => placeBalloons(wrapper, placed)
}

/**
 * Each balloon level with its passage, pushed down below the one above it.
 * Left is measured from the wrapper's middle, as the pages are centred in
 * it, so a wider or narrower frame keeps the balloons beside their page.
 */
function placeBalloons(wrapper: HTMLElement, notes: Note[]): void {
  const levels = notes
    .map((note) => ({ note, top: offsetWithin(note.anchor, wrapper) }))
    .sort((a, b) => a.top - b.top)
  let below = 0
  for (const { note, top } of levels) {
    const page = note.anchor.closest<HTMLElement>(`section.${PREFIX}`)
    const pageWidth = page?.offsetWidth ?? 0
    const placedTop = Math.max(top, below)
    note.balloon.style.top = `${placedTop}px`
    note.balloon.style.left = `calc(50% + ${(pageWidth - COMMENT_GUTTER) / 2 + PAGE_GAP}px)`
    below = placedTop + note.balloon.offsetHeight + BALLOON_GAP
  }
}
