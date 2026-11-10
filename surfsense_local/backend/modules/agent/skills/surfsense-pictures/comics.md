# Comics

A comic of any kind: one picture per page, or per panel for a scrolling one, every picture from the same character sheet and style line, bound into one PDF. Follow the set's steps in [`SKILL.md`](SKILL.md#a-set-of-pictures); this file is what is particular to comics.

## Which kind

Take the kind the user names; when they name none, a Western comic. The kind decides how it reads, how its pictures are shaped and bound, and how it looks. A style the user asks for (noir, chibi, watercolour, superhero) goes in the style line on top of it.

| Kind | Reads | Each picture | Binding (`pdf.md`) | Looks |
|---|---|---|---|---|
| Western comic | left to right | a `portrait` page of 4 to 6 panels | `LAYOUT = "pages"` | full colour, bold inks, caption boxes |
| Graphic novel | left to right | a `portrait` page of 3 to 6 panels | `"pages"` | as a Western comic, with room for quiet, wordless panels |
| Bande dessinée | left to right | a `portrait` page of 6 to 9 smaller panels | `"pages"` | detailed album pages, often clean "ligne claire" lines and flat colour |
| Manga | **right to left**: panel 1 top right, the last bottom left | a `portrait` page of 3 to 6 panels | `"pages"`, `DIRECTION = "rtl"` | black and white with screentone, speed lines, expressive faces |
| Manhua | left to right | a `portrait` page, or one panel a picture to scroll | `"pages"` or `"scroll"` | full colour, often painterly |
| Manhwa, webtoon | top to bottom, by scrolling | one panel or beat a `portrait` picture, no page | `LAYOUT = "scroll"` | full colour, soft shading, wide gutters between beats |
| Comic strip | left to right | one `landscape` picture of 3 or 4 panels in a row | `"pages"`, one page a strip | simple shapes, a punchline in the last panel |
| Yonkoma (4-koma) | top to bottom | one `portrait` picture of 4 equal panels stacked | `"pages"`, one page a strip | a manga strip: setup, development, turn, punchline |
| Picture book | left to right | one illustration a page, no bubbles | `"pages"`, every page's text as its lines | soft colour, one moment a page |
| Storyboard | left to right | one `landscape` frame a shot | `"pages"`, each shot's number and note as its lines | rough, sketchy frames; camera and movement in the note |

A manga's panels and bubbles still read right to left inside each page: say so in every prompt. Write its lines in the user's language, read left to right inside each bubble; ask for vertical lettering only when the user writes Japanese and asks for it.

## The plan

- **Length.** Four pages, or eight beats for a scrolling comic, when the user names none; at most twelve pictures, since each is billed or takes minutes. A comic strip or a yonkoma is one picture a strip.
- **Panels.** For each: where it sits (top, bottom left, wide), what it shows, and its lines. A scrolling comic has one beat a picture instead.
- **Lines.** One short line a bubble, at most about eight words, two or three bubbles a panel. A caption box for narration. Write every line in the plan, word for word: the PDF may need them. A picture book's and a storyboard's text is never in the picture; it goes under it.

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

For a manga: "Black-and-white manga page with screentone, read right to left. Panel 1 (top right): …". For a scrolling comic: "One tall webtoon panel, full colour, nothing else in the picture: …", one beat per picture. From the second picture on, add one line before the page: "Keep the characters looking exactly as in the reference picture: same faces, colours, clothes and drawing style. Draw a new page; do not copy its panels."

## Lettering

- **Bubbles drawn by the model.** Write each line in the prompt in quotes, in capitals for a Western comic.
- **A misspelt line is not redrawn.** Note the page; the PDF sets that page's lines under it, exactly, in a strip ([`pdf.md`](pdf.md)). A redraw would bill another picture for one letter.
- **On this computer** (the result says "Drawn on this computer"), **or when you cannot see the pictures**, draw every page without words: leave the bubbles out of the prompts, ask for "no text, no lettering, no speech bubbles", and give every page its strip. You cannot rely on the lettering, or check it.

## Before you bind

Look at every picture. Redraw or change one only when it is plainly wrong, such as a missing character, the wrong number of panels, panels in the wrong reading order, or a third arm, and say which and why. Then bind the PDF, every picture's name in `images`, in reading order, with the kind's `LAYOUT` and `DIRECTION`.
