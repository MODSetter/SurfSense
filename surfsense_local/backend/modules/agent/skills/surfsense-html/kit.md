# The figure kit

Put `<script data-kit="fig"></script>` before your own script and `surfsense_save_page` writes the kit there. Do not copy the kit into the page. Everything is on `Fig`; the code is `kit/fig.js` in this skill's folder.

World points are `[x, y, z]`: x and y on the floor, z up, in units of about one pixel of the real thing. Screen points are `[x, y]` in the SVG's `viewBox`. Give the `<svg>` class `fig`.

## Camera

| Call | Does |
|---|---|
| `Fig.fit(points, width, height, { pad, azimuth, elevation })` | A camera that fits these world points in the viewBox. Pass the **mechanism's** extremes, not a big empty floor, so it fills the frame. Defaults: true isometric (azimuth 45, elevation 35.264), `pad` 24. |
| `Fig.corners({ x, y, z, w, d, h })` | A box's eight corners, for `fit`. |
| `Fig.camera({ azimuth, elevation, scale, origin })` | A camera by hand. |
| `Fig.project(cam, point)`, `Fig.depth(cam, point)` | World to screen; larger depth is nearer the viewer. |

## Solids

Each returns a solid: its shaded sides, its top, an inked silhouette and, unless `bevel: false`, a glint along the top's front edges.

| Call | Draws |
|---|---|
| `Fig.box(cam, { x, y, z, w, d, h, r, tone, bevel })` | A box from floor corner `(x, y)` at height `z`: `w` along x, `d` along y, `h` up. `r` rounds its corners; use it on most parts, as real parts are rarely sharp. |
| `Fig.cylinder(cam, { cx, cy, z, r, h, steps, tone })` | A post, foot, knob, puck, coin or disc. |
| `Fig.prism(cam, ring, z, h, { tone, bevel })` | Any convex floor outline, counter-clockwise `[x, y]` points. `Fig.roundedRing` and `Fig.circleRing` make rings. |
| `Fig.shadow(cam, footprint, { z, spread })` | A soft contact shadow under `{x, y, w, d, r}` or `{cx, cy, r}`, painted first. One under the base grounds the whole figure. |
| `Fig.coil(cam, { from, to, r, turns })` | A spring between two world points, as `[back, front]`: list the back half before the rod it wraps and the front half after. |
| `Fig.wire(cam, points, { at })` | A cable or thin rod along world points, painted at depth `at`. |
| `Fig.line(cam, from, to)` | A path `d` between two world points. |

## Small parts on a solid

Each draws onto a solid and paints with it, right after its faces, so it is never hidden by the part it sits on. Each returns the solid.

| Call | Draws |
|---|---|
| `Fig.screws(cam, solid, points, { r })` | Screw heads with slots on its top, at floor points `[x, y]`. Put them at corners and where parts are fixed. |
| `Fig.dots(cam, solid, { x, y, w, d, cols, rows, r })` | A grid of holes on its top: a speaker, a vent, a keypad. |
| `Fig.ticks(cam, solid, { from, to, count, major, len, dir })` | A ruler's ticks between two world points; every `major`th is longer. |
| `Fig.knurl(cam, cylinder, { count })` | Grip grooves round a knob's visible side. |
| `Fig.onFace(cam, solid, origin, u, v, (pen) => …)` | Draw on any flat face. `origin` is a world point on it, `u` the direction of its width and `v` of its height. The pen draws in face units: `rect(s, t, w, h)`, `slots(s, t, w, h, count)`, `dot(s, t, r)`, `line(s1, t1, s2, t2)`, `text(words, s, t, { size, anchor })`. A top face is `u = [1, 0, 0]`, `v = [0, -1, 0]`; the face toward +x is `u = [0, 1, 0]`, `v = [0, 0, 1]`. |

## Painting

`Fig.svg(items, { sort })` returns the markup: solids, shadows, coil halves and wires, nested arrays flattened. By default it sorts by depth. Sorting cannot know every overlap, so for a mechanism list the parts back to front yourself and pass `{ sort: false }`: the base, then what stands on it from back to front, a spring's back half, the rod, its front half, then what sits on top. Paint the shadow first in its own call.

## Colour

`Fig.css` holds light neutrals as custom properties on `.fig`: `--fig-top`, `--fig-lit` and `--fig-shade` for faces, `--fig-edge` for outlines, `--fig-ink` for ticks and text, `--fig-hole`, `--fig-panel`, `--fig-glint` and `--fig-shadow`. Put it in a `<style>`. A solid's `tone` puts it in a group with class `fig-<tone>`, which sets its own: give the subject a tone in tints of the page's `--accent`, metal parts a cool grey, and keep the rest neutral, so the eye goes to what moves. Keep edges and ink in contrast with the faces.

## Motion

| Call | Does |
|---|---|
| `Fig.animate(element, tick)` | Calls `tick(dt, still)` each frame while `element` is on screen, until `tick` returns `true`. `dt` is seconds, clamped to 1/30. `still` is true under reduced motion: jump to the end state. Returns `wake()`: call it after input changes a target. |
| `Fig.follow(value, target, dt, tau)` | Eases toward the target; `tau` 0.1 to 0.3 s. |
| `Fig.spring(state, target, dt, stiffness, damping)` | A spring on `{ at, rate }`; returns `true` once settled. |
| `Fig.reducedMotion()` | Whether the reader asked for less motion. |

Redraw the whole figure in `tick`: building every solid again is cheap.

## Example: a spring scale

A base with a soft shadow, feet, corner screws, a ruler and an engraved plate; a rail between two end stops, one vented; a rod through a coil spring; a carriage, the subject, with screws, a knurled knob and a pointer on the ruler. The arrow keys add load, and the spring stretches by the scale's real stiffness. The page defines `--accent`.

```html
<figure class="card">
  <svg id="scale" class="fig" viewBox="0 0 720 420" tabindex="0" role="slider"
       aria-label="Spring scale: the arrow keys add or take away load"
       aria-valuemin="0" aria-valuemax="10" aria-valuenow="4" aria-valuetext="4 newtons, 32 millimetres"></svg>
  <figcaption>
    <span>Click the figure, then use the arrow keys</span>
    <span id="readout" role="status">load 4 N · stretch 32 mm</span>
  </figcaption>
</figure>
<script data-kit="fig"></script>
<script>
  document.head.insertAdjacentHTML("beforeend", `<style>${Fig.css}
    /* The subject in tints of the page's own --accent. */
    .fig-accent { --fig-top: color-mix(in srgb, var(--accent) 30%, white);
      --fig-lit: color-mix(in srgb, var(--accent) 65%, white); --fig-shade: var(--accent); }
    .fig-metal { --fig-top: #eef1f4; --fig-lit: #cfd5db; --fig-shade: #7d8790; }</style>`)
  const svg = document.getElementById("scale")
  const readout = document.getElementById("readout")
  const STIFFNESS = 8 // mm of stretch per newton
  const REST = -60    // the carriage's x with no load
  // Fit the mechanism, not empty floor, so it fills the frame.
  const cam = Fig.fit(Fig.corners({ x: -170, y: -60, z: -6, w: 340, d: 120, h: 70 }), 720, 420, { pad: 16 })
  let load = 4
  let x = REST + load * STIFFNESS

  function draw() {
    const base = Fig.box(cam, { x: -170, y: -60, w: 340, d: 120, h: 10, r: 10 })
    Fig.screws(cam, base, [[-156, -46], [156, -46], [-156, 46], [156, 46]])
    Fig.ticks(cam, base, { from: [-130, 34, 10], to: [130, 34, 10], count: 26, major: 5, len: 3 })
    Fig.onFace(cam, base, [70, 54, 10.1], [1, 0, 0], [0, -1, 0], (pen) => {
      pen.rect(0, 0, 70, 12)
      pen.text("SPRING SCALE  0–10 N", 4, 4, { size: 5 })
    })
    const feet = [[-152, -42], [152, -42], [-152, 42], [152, 42]]
      .map(([cx, cy]) => Fig.cylinder(cam, { cx, cy, z: -6, r: 8, h: 6, tone: "metal" }))
    const rail = Fig.box(cam, { x: -140, y: -7, z: 10, w: 280, d: 14, h: 5, r: 2, tone: "metal" })
    const stopL = Fig.box(cam, { x: -150, y: -18, z: 10, w: 16, d: 36, h: 34, r: 3 })
    Fig.onFace(cam, stopL, [-134, -12, 18], [0, 1, 0], [0, 0, 1], (pen) => pen.slots(0, 0, 24, 18, 4))
    const stopR = Fig.box(cam, { x: 134, y: -18, z: 10, w: 16, d: 36, h: 24, r: 3 })
    const rod = Fig.box(cam, { x: -134, y: -2, z: 26, w: x - 22 + 134, d: 4, h: 4, tone: "metal", bevel: false })
    const spring = Fig.coil(cam, { from: [-134, 0, 28], to: [x - 22, 0, 28], r: 9, turns: 9 })
    const carriage = Fig.box(cam, { x: x - 22, y: -22, z: 15, w: 44, d: 44, h: 26, r: 4, tone: "accent" })
    Fig.screws(cam, carriage, [[x - 15, -15], [x + 15, -15], [x - 15, 15], [x + 15, 15]])
    const knob = Fig.cylinder(cam, { cx: x, cy: 0, z: 41, r: 9, h: 10, tone: "metal" })
    Fig.knurl(cam, knob)
    const pointer = Fig.box(cam, { x: x - 1.5, y: 22, z: 15, w: 3, d: 14, h: 2, tone: "accent", bevel: false })
    svg.innerHTML =
      Fig.svg([Fig.shadow(cam, { x: -170, y: -60, w: 340, d: 120, r: 10 }, { z: -6, spread: 6 })]) +
      Fig.svg([...feet, base, rail, stopL, stopR, spring[0], rod, spring[1], carriage, knob, pointer], { sort: false })
  }

  const wake = Fig.animate(svg, (dt, still) => {
    const target = REST + load * STIFFNESS
    x = still ? target : Fig.follow(x, target, dt, 0.25)
    if (Math.abs(x - target) < 0.05) x = target
    draw()
    return x === target
  })

  svg.addEventListener("keydown", (event) => {
    const moves = { ArrowRight: load + 1, ArrowLeft: load - 1, Home: 0, End: 10 }
    if (!(event.key in moves)) return
    event.preventDefault()
    load = Math.max(0, Math.min(10, moves[event.key]))
    const said = `load ${load} N · stretch ${load * STIFFNESS} mm`
    readout.textContent = said
    svg.setAttribute("aria-valuenow", String(load))
    svg.setAttribute("aria-valuetext", said)
    wake()
  })
  draw()
</script>
```
