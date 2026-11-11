---
name: surfsense-pictures
description: Draw pictures with surfsense_make_image - one picture or infographic, or a set that belongs together, such as a comic, a manga, a manhwa or webtoon, a comic strip, a graphic novel, a storyboard or a picture book, bound into one comic with surfsense_bind_comic. Load it whenever the user asks for a picture, an illustration, or any set of pictures, or for a change to one you drew. Not for charts of numbers, and not for a web page.
---

# Pictures

`surfsense_make_image` draws with the user's image model and keeps each picture in Studio, named `image-<id>`. This skill is how to use it well.

## The files in this skill

| File | Read it |
|---|---|
| `comics.md` | For any kind of comic (Western, manga, manhwa and webtoon, manhua, strip, yonkoma, graphic novel, bande dessinée), a picture book or a storyboard: how each reads, is laid out, is lettered and is bound. |

## One picture

1. Read any sources the picture draws on first.
2. Write one self-contained prompt: the subject, the setting, the style, the light, what is in front and what is behind. As short as it can be while still saying what to draw.
3. Choose `shape` when it matters: `portrait` for a page or a poster, `landscape` for a banner or a strip, `square` for an icon. Choose `type: infographic` when the picture sets out facts, in Studio's sketchnote style; leave `type` out for any other picture.
4. Look at what comes back. Image models get hands, counts and lettering wrong. Change it once with its `artifact_id` when it is plainly wrong, and say what you changed; otherwise tell the user what is off.

No picture for numbers: a chart stays a chart, in a document. Keep any words in a picture short, a title or a label; text that must be exact goes in the document around it.

## A set of pictures

A comic, a storyboard, a picture book, or any pictures that must look like one set:

1. **Plan** the set: what each picture shows, in order. Write a **character sheet**, each character's face, hair, build, clothes and colours in a few fixed words, and a **style line**: medium, palette, line weight. Both go word for word into every prompt.
2. **Confirm once.** Say how many pictures, the plan in short, and that each is billed by their provider, or takes minutes on their computer. On yes, draw every picture without asking again. A single picture needs no confirmation.
3. **Draw the first alone,** and look at it. When it is wrong, change it before going on: every later picture copies its characters.
4. **Draw the rest with the first as their reference**: `references: ["image-<first>"]`. Give each its own call, all in one step, so a remote model draws them side by side. A character picture the user gave, or a character sheet they asked for first, is the reference instead.
5. **Title each** "<title> · page <n>", or "· scene <n>": a chat cannot reuse a picture's title.
6. **Bind them** with `surfsense_bind_comic`, every picture's name in reading order, with the `layout` and `direction` [`comics.md`](comics.md#which-kind) gives its kind. The comic is what the user keeps: one artifact in Studio, a PDF.
7. **Answer** with the comic and one line per picture, so the user can ask for "page 3 again".

## When the model cannot take a picture in

Some image models draw from words alone. Nothing is refused, and nothing needs setting up:

- A reference is drawn from the words alone. The result says so: then every picture's character sheet carries the likeness, and in the plan you confirm, say once, plainly, that characters may differ a little between pictures.
- A change is drawn again from the picture's prompt and the change, and may not keep the rest. The result says so; tell the user in one line.

Never send the user to Settings for this.

## Changing a set later

Change one picture with its `artifact_id`, then call `surfsense_bind_comic` with the comic's `artifact_id` and every page, the new picture's name in place of the old: that is the comic's next version. To add a picture, draw it with the first as reference and bind again.
