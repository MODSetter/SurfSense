import {
  $getRoot,
  $getSelection,
  $isRangeSelection,
  type LexicalEditor,
} from "lexical"

// jsdom has no contenteditable editing for Lexical to read, so what user-event
// types goes in through the editor, as a browser's input pipeline would put it.
function $writable() {
  const selection = $getSelection()
  if ($isRangeSelection(selection)) return selection
  $getRoot().selectEnd()
  const ended = $getSelection()
  return $isRangeSelection(ended) ? ended : null
}

// Nor focus from a selection, which is how Lexical focuses its editable root.
const select = Selection.prototype.setBaseAndExtent
Selection.prototype.setBaseAndExtent = function (...args) {
  const [anchor] = args
  const element = anchor instanceof Element ? anchor : anchor.parentElement
  element?.closest<HTMLElement>("[data-lexical-editor]")?.focus()
  select.apply(this, args)
}

function editorOf(target: EventTarget | null) {
  return (target as (HTMLElement & { __lexicalEditor?: LexicalEditor }) | null)
    ?.__lexicalEditor
}

// Nor a ClipboardEvent, which Lexical reads a paste's text through. A file passes:
// the composer's own paste command takes those.
document.addEventListener(
  "paste",
  (event) => {
    const editor = editorOf(event.target)
    const pasted = event.clipboardData
    if (!editor || !pasted || pasted.files.length > 0) return
    event.preventDefault()
    event.stopImmediatePropagation()
    editor.update(() => $writable()?.insertRawText(pasted.getData("text")), {
      discrete: true,
    })
  },
  true
)

function writeLikeABrowser(event: Event) {
  const editor = editorOf(event.target)
  if (!editor) return
  const { inputType, data } = event as InputEvent
  event.preventDefault()
  event.stopImmediatePropagation()
  if (!editor.isEditable()) return
  editor.update(
    () => {
      const selection = $writable()
      if (inputType === "insertText" && data) selection?.insertRawText(data)
      else if (inputType === "deleteContentBackward") {
        selection?.deleteCharacter(true)
      }
    },
    { discrete: true }
  )
}

// On the root, once per root and after what the app put there: its listeners see a
// write first, as they would in a browser, and can refuse it.
const writing = new WeakSet<EventTarget>()
document.addEventListener(
  "beforeinput",
  ({ target }) => {
    if (!target || !editorOf(target) || writing.has(target)) return
    writing.add(target)
    target.addEventListener("beforeinput", writeLikeABrowser, true)
  },
  true
)
