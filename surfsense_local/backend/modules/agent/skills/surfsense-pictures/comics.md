# Comics

A comic, a manga, a comic strip, a storyboard or a picture book: one picture per page, every page from the same character sheet and style line, bound into one PDF. Follow the set's steps in [`SKILL.md`](SKILL.md#a-set-of-pictures); this file is what is particular to comics.

## The plan

- **Pages.** Four when the user names no number; at most twelve, since each is billed or takes minutes. A comic strip is one `landscape` picture of three or four panels.
- **Panels.** Two to five a page. For each: where it sits (top, bottom left, wide), what it shows, and its lines.
- **Lines.** One short line a bubble, at most about eight words, two or three bubbles a panel. A caption box for narration. Write every line in the plan, word for word: the PDF may need them.

## A page's prompt

The style line, the character sheet, then the page, laid out as the image model reads it best:

```text
Full-colour comic book page, clean bold ink lines, flat colours, white gutters,
black-bordered panels, speech bubbles with clear hand-lettered capitals.
Characters: MILO, a small orange tabby cat with a white chest, green eyes and a red
scarf. NORA, a woman about seventy, short white hair, round glasses, yellow raincoat.
Page 2 of 4 of the comic "The Lighthouse Cat". A portrait page of 3 panels:
Panel 1 (wide, top): a fishing boat tosses on huge waves at night.
Panel 2 (bottom left): NORA taps the dead lamp. NORA says: "THE BULB IS BROKEN!"
Panel 3 (bottom right): MILO spots a box of spare bulbs on a high shelf.
```

From page 2 on, add one line before the page: "Keep the characters looking exactly as in the reference picture: same faces, colours, clothes and drawing style. Draw a new page; do not copy its panels." Every page is `shape: portrait`.

## Lettering

- **Bubbles drawn by the model.** Write each line in the prompt in quotes, in capitals.
- **A misspelt line is not redrawn.** Note the page; the PDF sets that page's lines under it, exactly, in a strip ([`pdf.md`](pdf.md)). A redraw would bill another picture for one letter.
- **On this computer** (the result says "Drawn on this computer"), **or when you cannot see the pictures**, draw every page without words: leave the bubbles out of the prompts, ask for "no text, no lettering, no speech bubbles", and give every page its strip. You cannot rely on the lettering, or check it.

## Before you bind

Look at every page. Redraw or change one only when it is plainly wrong, such as a missing character, the wrong number of panels, or a third arm, and say which and why. Then bind the PDF, every page's name in `images`, in order.
