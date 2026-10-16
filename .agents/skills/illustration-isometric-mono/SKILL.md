---
name: illustration-isometric-mono
description: Draws true-isometric diorama illustrations of developer and design workspaces in one green ramp, generated as SVG with a bundled scene kit. Traits: one rounded off-white slab with a faceted bevelled edge; every face filled by the way it faces (top lightest, right darkest) from five greens; 0.9 deep-green outlines on every edge; dense fine repeated detail (rack units, ribs, vents, keys, code lines); soft green shadows and glows on the slab. Covers projection, shading, line weights, object vocabulary, layout and the iso.mjs kit (racks, databases, laptops, containers, cards, badges, books, plants, cables, status tower). Use when someone asks for isometric illustration, an iso scene, 2.5D tech art, monochrome or green isometric art, a server room, dev stack or cloud picture, or art for empty states, onboarding, 404 pages, blog headers, feature spots or marketing cards in this style.
---

# Illustration: Isometric mono

A small world on a slab: seven to ten developer or design objects arranged on one rounded platform, drawn in true isometric with a single green ramp, every edge inked and every face shaded by its orientation. It reads as a precise, technical, calm product illustration, and suits infrastructure, tooling and workflow subjects: dev stacks, pipelines, studios, data centres.

Boundary: there are no people here. For a character acting out a tech moment use `illustration-flat-with-black` or `illustration-outlined-cartoon`; for one hero object with a hard offset shadow and floating extras use `illustration-teal-spot`; for chunky navy-extruded pop geometry use `illustration-bold-pop`.

Extracted from a set of 42 original design-and-coding cards in 14 styles; the three cards in examples/ are this style's shipped cards. Design Studio and CI Pipeline both scored 8.5 on their first judged round; both were built on the kit that ships in `scripts/iso.mjs`.

## The look in one sentence
Every surface is a flat face of a true-isometric solid, filled from one green ramp by the direction it faces and outlined in 0.9 deep green, standing on a single bevelled off-white slab with soft green light pooled around it.

## Palette

| Role | Hex | Where it goes |
|---|---|---|
| Card background | `#ffffff` | No background rect; the slab floats on white |
| Outline | `#0f3d30` | Every visible edge (0.9), insets and panels (0.5–0.55), tiny parts (0.35–0.45) |
| Off-white | `#fbf8f1` | Slab top, top faces of light and mid objects, label plates, paper |
| Pale mint | `#c9f3d6` | Slab chamfer, lit LEDs, highlighted code lines, trackpads, tape |
| Mint | `#8de8a6` | Left (+y) faces of light objects, slab band, code lines, leaf faces |
| Mid green | `#5cc58a` | Right (+x) faces of light objects, left faces of mid objects, glows, detail lines |
| Deep green | `#2f9e6c` | Right faces of mid objects, keys, shadow starts, fine ribs, slab bottom bevel |
| Very deep | `#0b4a3a` | Screens, keyboards' wells, rack units, mug interiors, terminal cards |

- Faces get colour from `shade(normal, material)`, which blends top/left/right colours by the face normal. Curved and rotated faces therefore produce in-between hexes (50–140 per card). They are correct; check them with `scripts/ramp-check.mjs`, not by eye. `lint.mjs --palette` lists them all as warnings by design.
- Materials (top / left / right): `M.light` off-white / mint / mid (default objects), `M.pale` off-white / pale / mint (plugs, coasters), `M.mid` off-white / mid / deep (racks, monitors, pots, cabinets), `M.deep` very deep / mid / deep (flat dark cards), `M.dark` deep / deep / very deep.
- Opacity only on floor decals (shadows, glows, the slab's under-shadow), screen sheens (`#5cc58a` 0.16–0.22) and highlight bands. No other hue ever: no greys, no accent colour, no text colour outside the ramp.

## Line and fill
Numbers in SVG units at 480 wide (the kit already scales plan units by K = 0.91).

- **Outline 0.9 `#0f3d30`** on every visible edge of every solid, drawn once per edge (`poly3`, `prismZ` and `platform` do this). Round joins and caps.
- **Face fills** carry a 0.35 stroke in their own colour so neighbouring faces don't show hairline gaps. Do the same whenever you `fillP` a face yourself.
- **Panels and insets** 0.5–0.55 (door insets at stroke-opacity 0.7, plinth lines at 0.6). **Tiny parts** (plugs, corner castings, swatches) 0.35–0.45.
- **Detail lines in ramp greens:** ribs and vents 0.45–0.6 in `#2f9e6c` or `#0b4a3a` (opacity 0.55–0.75 on the right faces), container ribs every 2.6, vents every 2.2, rack units every 6.4 with LEDs r 0.7–0.8, book page lines every 1.15, code lines 1.0–1.2 in pale/mint/mid on very deep screens, a `>_` prompt at 2.4.
- **Platform:** inner rim `#5cc58a` 0.6 at opacity 0.75, 6.5 inside the edge; bevel seams 0.5 at opacity 0.55; a soft under-shadow `#5cc58a` at 0.2 offset 4 and blurred 4.
- **Cables:** three strokes along one Catmull-Rom curve: outline 3.0, mid green 1.55, a 0.5 mint highlight offset (−0.35, −0.45). A thinner gauge: 2.46 and 1.09.

## Characters
This style draws no people. The hero-object rules take their place:
- **One hero**, usually at the slab centre (plan x and y within ±30): a laptop with code, a monitor with a design tool, a conveyor. It carries the most detail and gets a mid-green glow in front of it (`glow(..., 0.5)` about 52 x 30). A hero that is a tall row (a rack row) runs along an upper edge instead, with its glow on the floor in front of it.
- **Supporting objects** are 40–70% of the hero's footprint and each tells one part of the subject. Build every one from boxes, rounded prisms, cylinders and extrusions; nothing is a flat icon stuck on the slab except deliberate flat cards (z ≤ 3).
- **Every object has one face of fine repeated detail** (units, ribs, keys, pages, slats) and at least one glyph that names it (`</>`, a tick, an upload arrow, a `>_`).
- **Heights vary in four bands:** flat 2–3 (cards, sketchbooks), low 18–30 (mugs, books, containers), mid 40–60 (cabinets, gates), tall 68–90 (racks, shelves, towers, monitors). Tall pieces stand only along the upper edges; a row of identical racks counts as one piece.

## Decor and props
- **Kit props** (`scripts/iso.mjs`): `rack`, `database`, `laptop`, `container`, `mug`, `card` (terminal), `cloudBadge`, `books`/`book`, `plant`, `tower` (status lights), `cable` with `cableShadow`. Primitives: `box`, `rbox` (rotated), `prismZ` over `rring`/`circle` (rounded slabs, cylinders), `poly3` (any convex solid), `extrude` (standing badges and icons), `textOn`. Detail helpers: `hatch`, `dotGrid`, `fan`.
- **Example-only props** worth copying from the generators' structure: monitor with design UI, shelf, drawing tablet, sketchbook, pen cup, swatches, mood board (Design Studio); conveyor, gates, robot arm, pallet stack, dashboard card, rocket badge (CI Pipeline). Read them in `examples/*.svg` for layout and detail density.
- **Reuse with care:** take at most three kit props straight from any one example; build the rest for the subject from primitives (a cooling unit is a box with `fan` and `hatch`, a drive crate is an open box with thin boxes inside, gas cylinders are `prismZ` cylinders with a label band).
- **Floor light:** a cast shadow for every object; a dark contact pool (`#2f9e6c` at 0.3–0.34) under every small object; one to four mid-green glows (0.46–0.6) in front of screens, LEDs and lit panels; `halo()` for lamps and stack lights.
- **Text:** none, or at most two monospace labels laid on a face with `textOn()` (`ui-monospace` 5.6, weight 700, pale mint on very deep). Draw glyphs as lines.
- **Never:** people, sky, background shapes, a second slab, floating objects off the slab, sparkles, confetti, any non-green hue, perspective.

## Composition
- One slab: `platform()` with half size 122 and corner radius 26 in plan units. It projects to x 55.5–424 (77% of the card width), its bottom edge at y 330.5. With objects the ink box is 368.5 x 287–297: margins left and right 56, bottom 30, top 34–44.
- Card ink coverage 22–24%. Seven to ten objects (a flat floor element such as tiles or a card counts) with 12–25 plan units between footprints; keep every footprint within ±110 so it stays clear of the rim line.
- Where plan points land on the card: `screen x = 240 + 0.788·(x − y)`, `screen y = 204 + 0.455·(x + y) − 0.91·z`.

| Slab part | Plan | Card |
|---|---|---|
| Back corner (top) | (−122, −122) | (240, 93) |
| Left corner | (−122, 122) | (48, 204) |
| Right corner | (122, −122) | (432, 204) |
| Front corner (bottom) | (122, 122) | (240, 315) |
| Upper-left edge / upper-right edge | x = −122 / y = −122 | |

- Depth runs from the back corner (small x + y) to the front corner (large x + y). Put tall pieces along the two upper edges, flat cards and small items toward the left, right and front corners. Fill all four quadrants of the slab.
- **The slab centre (plan 0, 0; card 240, 204) always holds an object.** Usually that is the hero. When the subject is itself a tall row (racks, shelves), the row runs along an upper edge and a low object takes the centre; an empty centre reads as a hole.
- **Spread objects in screen x, not just in plan.** Objects with similar `x − y` stack in one column on the card and overlap each other; give neighbours in depth different `x − y`.
- Leave at least 4 px on the card between neighbouring silhouettes, or overlap them clearly; a cylinder top just kissing a base plate reads as a tangent.
- One or two cables tie the hero to back objects and lie on the slab (z 1.1), climbing into ports at the ends.
- Light comes from −x (upper left): every shadow falls toward +x (lower right).

## Techniques

**1. The projection and the shading come from the kit.** Plan coordinates `(x, y, z)` map with `P(x, y, z) = [240 + (x − y)·cos30°·0.91, 204 + ((x + y)/2 − z)·0.91]`. Build solids and let the kit pick each face's fill:

```js
import * as I from '/abs/path/illustration-isometric-mono/scripts/iso.mjs';
I.init('dc-'); I.floorDefs(); I.platform();
// ...every castShadow / glow / cableShadow, then I.flushFloor() (technique 3)...
I.box(-20, 20, -30, 30, 0, 40, I.M.mid);                                   // a cabinet
I.prismZ(I.rring(60, 60, 18, 12, 3, 0, 3), 0, 3, I.M.deep);                 // a rounded flat card
I.prismZ(I.circle(-60, 60, 12, 12), 0, 24, I.M.light);                      // a cylinder
```

**2. Draw on faces with face mappers.** `onLeft(y)` maps `(x, z)` onto the +y face, `onRight(x)` maps `(y, z)` onto the +x face, `onTop(z)` maps `(x, y)`. Combine with `quad()` and `line()`:

```js
const F = I.onLeft(30);                                                    // front (+y) face of the cabinet
I.both(I.D(I.quad(F, -16, 4, 16, 36)), I.VD, I.OUT, 0.5);                  // dark door panel
let ribs = ''; for (let x = -13; x <= 13; x += 2) ribs += I.line(F, [[x, 8], [x, 32]]);
I.strokeP(ribs, I.DG, 0.5);                                                // fine repeated detail
```

**3. Floor first, then objects back to front.** All `castShadow`, `glow` and `cableShadow` calls go before `flushFloor()`, which clips them to the slab and blurs them by 1.6. Shadow length is `h · 0.62` plan units toward +x; for very tall objects pass `h · 0.35–0.45` so the shadow doesn't run off the slab.

```js
I.castShadow(I.rectFoot(-20, 20, -30, 30), 40, 0.62, 0.24);                // footprint, height, length k, alpha
I.glow(60, 60, 26, 20, I.DG, 0.32);                                        // contact pool under a small object
I.glow(0, 50, 52, 30, I.MG, 0.5);                                          // screen spill in front of the hero
I.flushFloor();
```

Then draw objects in ascending `x + y` of their footprint centres. When one object reaches both behind and in front of another (a conveyor through gates, a robot arm over a belt), split it into back and front calls, as the CI Pipeline card does.

**4. Fine repeated detail has helpers.** `hatch(F, u0, u1, w0, w1, step, dir, colour, width)` draws ribs, slats, vents, bays and louvres inside a face rectangle (`dir 'w'` lines run along w, `'u'` along u); `dotGrid(F, ...)` draws perforations and cork; `fan(F, uc, wc, r)` draws a round fan grille. Put each feature on a face that has open slab in front of it: a +x face needs clear slab toward +x, a +y face toward +y. A fan drawn on a +x face six units from a taller rack was hidden entirely. Reserve a clear strip on a face for a cable socket; a socket drawn over a battery panel looks like a mistake.

```js
const R = I.onRight(-90);                                                  // +x face of a cooling unit at x = -90
I.fan(R, -46, 34, 13);                                                     // fan centred at y -46, z 34
I.hatch(R, -62, -30, 7, 18, 2.2, 'u', I.DG, 0.5);                          // louvres under it
I.dotGrid(I.onTop(1.2), -82, -70, -64, -54, 2.4, I.DG, 0.7, 0.7);          // perforated floor tile
```

**5. Standing shapes are extrusions.** For a badge, logo or icon standing on the slab, describe its outline in `(u, w)` and pass a front-face mapper to `extrude()` (or copy `cloudBadge()`): side walls are sorted and shaded automatically, concave notches get crease lines.

A full worked card: `scripts/dev-stack.gen.mjs` rebuilds `examples/dev-stack.svg` from a layout table (identical to within anti-aliasing). Start every new card by copying it.

## Failure modes
- **Objects float.** The first Dev Stack round had no cast shadows or contact pools and every object looked pasted on; give each object a `castShadow` and each small one a dark pool.
- **Wireframe objects.** An early container drawn as outlines and ribs read as a cage; fill every face from a material.
- **Empty slab region.** The first layout left the front right quarter bare; spread seven to ten objects over all four quadrants.
- **Empty centre.** With the racks along the back edge, a first Data Center layout left plan (0, 0) bare and the card read as a ring of objects round a hole; put a low object there.
- **A column of objects.** Three props placed at different plan depths but the same `x − y` stacked on top of each other on the card; vary `x − y`.
- **Detail on a hidden face.** A fan grille on a face that a taller neighbour covers is wasted; check which faces stay visible before decorating.
- **The slab floats.** Removing the platform's blurred under-shadow makes the whole diorama hover; keep `platform()` intact.
- **Painter's order wrong.** An object drawn after a nearer one covers it; sort by `x + y` and split straddling objects. Open containers (crates, trays, shelves) need three passes: the box and its dark opening, then the contents back to front, then the near walls (+y and +x faces) and their top rims again. Drawn in one pass, drives in a crate hung in front of its front wall.
- **A rearranged example.** A first Data Center draft reused six kit props from Dev Stack (card, books, cloud, database, rack, mug) and read as Dev Stack moved around; use at most three props from any one example and build the rest for the subject.
- **Shadows in two directions.** Mixed light reads as a mistake at once; every shadow goes toward +x.
- **Hairline seams between faces.** A face filled without its 0.35 self-coloured stroke shows a white crack against its neighbour at 2x.
- **Heavy or uneven lines.** Edges thicker than 0.9 turn it into an icon set; detail heavier than 0.6 clogs. Keep the two tiers.
- **Coarse detail.** Plain boxes without ribs, units or keys read as a low-detail stock icon; every object needs one face of fine repeats.
- **A non-green colour.** Any accent hue breaks the monochrome; `ramp-check.mjs` fails on it.
- **Fake isometric.** Angles from a 2:1 pixel grid or a perspective camera don't match the kit's 30°; only ever place points through `P()`.
- **Text instead of glyphs.** Words on objects look like labels on a diagram; draw `</>`, ticks and arrows as lines.

## Examples
- `examples/dev-stack.svg`: "Dev Stack". A laptop with code cabled to two server racks, a database stack, a shipping container, a terminal card, a cloud upload badge, books and a mug. Shows racks, cylinders, the laptop screen UI, cables and contact pools. Rebuilt by `scripts/dev-stack.gen.mjs`.
- `examples/design-studio.svg`: "Design Studio". A monitor running a design tool on a stand, a drawing tablet with stylus, a bookshelf, a mood board, a sketchbook, swatches, a pen cup, a snake plant and a mug. Shows screen UI on a vertical face, leaning books and frames, the plant leaves.
- `examples/ci-pipeline.svg`: "CI Pipeline". Code boxes ride a conveyor out of a repo cabinet through build and test gates to a robot arm that stacks them on a pallet, with a status tower, a container, a dashboard card and a rocket badge. Shows split back/front drawing, text on a face, halos and a story told left to right.

## Workflow
Run every command from the skill folder (the folder that holds this file).

1. **Brief.** Name the subject and list seven to ten objects that tell it, with one hero. Say what glyph names each object.
2. **Layout table.** Copy `scripts/dev-stack.gen.mjs` to your work folder as `card.gen.mjs`, change its import to `scripts/iso.mjs` by absolute path, and replace the layout table: footprints in plan units within ±110, heights in the four bands, tall pieces along the upper edges, something at the centre. Before drawing, convert each footprint centre to card coordinates with the formula in Composition and check that no two objects share a screen column.
3. **Floor.** One `castShadow` per object, contact pools for small objects, one to four glows, cable shadows, then `flushFloor()`.
4. **Objects back to front.** Kit props first; write new props as functions in `card.gen.mjs` from `box`, `prismZ`, `poly3`, `extrude` and face mappers, each with one face of fine detail and one glyph.
5. **Render:** `node /path/card.gen.mjs card.svg "Card Title" && node scripts/render.mjs card.svg card.png`
6. **Sheet with the examples:** `node scripts/render.mjs --sheet sheet.png examples/*.svg card.svg`. Ask "same kit, same set?"
7. **Zoom** each object at 4–6x: `node scripts/render.mjs card.svg z-obj.png --zoom x,y,w,h --scale 6`. Check seams, outline weights, painter's order, shadow contact, cable ends in their ports.
8. **Critique** on the five criteria in references/craft.md (criterion 2 becomes "object drawing": construction, detail density, glyphs). Fix and repeat from step 5; expect three or four rounds.
9. **Lint and colour check:** `node scripts/lint.mjs card.svg --prefix xx-` must PASS, then `node scripts/ramp-check.mjs card.svg` must report 0 strays.

## Verify
- [ ] Every point comes from `P()`: edges run at exactly ±30° or vertical.
- [ ] One slab, 368.5 wide, side margins 56, bottom margin 30; nothing leaves the slab.
- [ ] Seven to ten objects in all four quadrants, one at the slab centre; tall pieces along the upper edges.
- [ ] Each face's fill matches its orientation: top lightest, +y face mid, +x face darkest (dark `M.deep` slabs excepted).
- [ ] Every visible edge is outlined at 0.9; all detail strokes are 0.6 or finer (except code lines, glyph strokes, bars and cables).
- [ ] No white hairline cracks between faces at 4x.
- [ ] Every object casts a shadow toward the lower right; small objects sit in a dark contact pool.
- [ ] The hero has a mid-green glow in front of it and the most detail.
- [ ] Every object has a face of fine repeated detail and a glyph that names it, on a face with open slab in front of it.
- [ ] No two silhouettes kiss: 4 px or more apart on the card, or clearly overlapped.
- [ ] Cables lie on the slab and end inside a plug on a face.
- [ ] No people, no non-green hue, at most two monospace labels.
- [ ] `ramp-check.mjs` reports 0 strays and `lint.mjs --prefix` passes.
- [ ] The subject reads at 1x from the objects alone.