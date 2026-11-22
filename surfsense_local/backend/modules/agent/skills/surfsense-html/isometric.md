# Drawing isometric figures

A figure is drawn with `ISO`, a short helper you copy into the page whole, then use from your own script. It turns world points into an isometric drawing: solids shaded by the way they face, an inked outline, a glint on the top edges, soft shadows, and calm motion. Nothing is loaded from anywhere; the helper is plain code in the page.

Before you write a figure, read the one file in `examples/` closest to your mechanism: it is a complete page using this helper, and the quickest way to a good figure is to start from it.

## The world

- Points are `[x, y, z]`: `x` and `y` on the floor, `z` up, in units of about one pixel of the real thing. A base of 300 to 400 units, parts of 10 to 60, screws of 2 or 3.
- The camera is true isometric. `ISO.fit(camera, points, width, height, pad)` scales and centres it so those points fill the `viewBox`. Pass the corners of the base and the tallest part, never a large empty floor: the mechanism should fill the frame.
- Larger `ISO.depth(camera, point)` is nearer the viewer. From the default camera, larger `x` and larger `y` are nearer.

## The helper

| Call | Gives |
|---|---|
| `ISO.camera()` then `ISO.fit(cam, points, w, h, pad)` | The camera, fitted to the figure. |
| `ISO.box(cam, { x, y, z, w, d, h, r, tone })` | A box from floor corner `(x, y)` at height `z`: `w` along x, `d` along y, `h` up; `r` rounds its corners. Most real parts are rounded a little. |
| `ISO.cyl(cam, { x, y, z, r, h, tone })` | An upright cylinder: a foot, post, knob, pin, coin, light or screw head. |
| `ISO.prism(cam, ring, z, h, tone)` | Any convex floor outline raised by `h`; `ISO.rect` and `ISO.circle` make outlines. |
| `ISO.shadow(cam, ring, z)` | A soft shadow under a footprint, painted first. One under the base grounds the figure. |
| `ISO.line(cam, a, b, cls)` | A line between world points: ticks, seams, slots, a shear line. |
| `ISO.path(cam, points, close)` | An SVG path through world points, for parts of your own: a spring, a cable, a curve. |
| `ISO.draw(parts, sort)` | The parts' SVG, back to front by depth; `sort = false` keeps your order. |
| `ISO.follow(value, target, dt, tau)` | Eases toward a target by elapsed time. |
| `ISO.animate(element, tick)` | Calls `tick(dt)` each frame while the figure is on screen, until it returns `true`; returns `wake()` to start it again after input. |
| `ISO.still()` | Whether the reader asked for reduced motion: jump to the end state. |

Each solid is `{ at, svg }`. Add a detail to the part it sits on with `part.svg += ...`, so it paints with that part and is never hidden by it: screws on a plate, ticks on a ruler, slots on a housing, a progress bar on a desk.

## Painting order

`ISO.draw` sorts by each part's centre, which is right for parts of similar size. It is wrong where a long part meets small ones: the middle of a long belt is nearer than a parcel on its far end, so sorting alone paints the belt over the parcel. Paint in layers instead, each its own `ISO.draw` call:

1. the shadow;
2. the base;
3. long parts that others stand on (a belt, a rail, a plug), in your own order with `sort = false`;
4. everything standing on them, sorted.

A part that wraps another (a spring round a rod, a frame round a carriage) is drawn in two halves: the back half before it and the front half after. The spring scale example shows how.

## Colour

Every colour is a CSS custom property. Each part has a `tone`, a class that sets three: `--top` for its top, and `--lit` and `--shade`, which its sides are mixed from. Keep the figure light, like the page:

- the subject, the part the idea is about, in tints of the page's accent;
- metal parts in cool greys, the base and housings in warm neutrals;
- states as tones: a green light for free, amber for busy, the subject turning green when it works.

```css
svg.fig { display: block; width: 100%; height: auto; border-radius: 10px; background: var(--stage); }
.fig { --edge: #3d3a34; }
.fig .top { fill: var(--top); stroke: var(--edge); stroke-width: .6; }
.fig .edge { fill: none; stroke: var(--edge); stroke-width: 1; }
.fig .glint { fill: none; stroke: #fff; stroke-width: 1; opacity: .85; }
.fig .ink { fill: none; stroke: var(--edge); stroke-width: .7; }
.fig .shadow { fill: rgba(40, 34, 26, .2); filter: blur(4px); }
.fig path { stroke-linejoin: round; }
.plate { --top: #f3efe6; --lit: #e3ddd0; --shade: #b7ae9c; }
.metal { --top: #eef1f4; --lit: #cfd5db; --shade: #7c8690; }
.subject { --top: /* a light tint of the accent */; --lit: /* the accent, lighter */; --shade: /* the accent */; }
```

## The code to copy

Copy this whole block into the page's script, before your figure's code. Change nothing in it.

```js
// ISO: an isometric drawing helper. Copy it whole into the page; draw with it below.
const ISO = (() => {
  const R = Math.PI / 180
  // A camera looking down at the floor (x, y) from elevation degrees, turned azimuth degrees.
  const camera = (azimuth = 45, elevation = 35.264) => ({
    ca: Math.cos(azimuth * R), sa: Math.sin(azimuth * R),
    ce: Math.cos(elevation * R), se: Math.sin(elevation * R), s: 1, ox: 0, oy: 0,
  })
  const turn = (c, x, y) => [x * c.ca - y * c.sa, x * c.sa + y * c.ca] // [across, toward viewer]
  const project = (c, [x, y, z]) => {
    const [u, t] = turn(c, x, y)
    return [c.ox + u * c.s, c.oy + (t * c.se - z * c.ce) * c.s]
  }
  const depth = (c, [x, y, z]) => turn(c, x, y)[1] * c.ce + z * c.se // larger is nearer
  // Scale and centre the camera so these world points fill a w x h viewBox.
  function fit(c, points, w, h, pad = 20) {
    Object.assign(c, { s: 1, ox: 0, oy: 0 })
    const f = points.map((p) => project(c, p))
    const xs = f.map((p) => p[0]), ys = f.map((p) => p[1])
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
    c.s = Math.min((w - 2 * pad) / (x1 - x0), (h - 2 * pad) / (y1 - y0))
    c.ox = (w - (x1 - x0) * c.s) / 2 - x0 * c.s
    c.oy = (h - (y1 - y0) * c.s) / 2 - y0 * c.s
    return c
  }
  const xy = (c, p) => project(c, p).map((n) => n.toFixed(1)).join(" ")
  const path = (c, points, close = true) => "M" + points.map((p) => xy(c, p)).join("L") + (close ? "Z" : "")
  // Floor outlines, counter-clockwise: a rectangle with corners rounded by r, a circle.
  function rect(x, y, w, d, r = 0) {
    r = Math.min(r, w / 2, d / 2)
    if (!r) return [[x, y], [x + w, y], [x + w, y + d], [x, y + d]]
    const ring = []
    for (const [cx, cy, a] of [[x + w - r, y + r, -90], [x + w - r, y + d - r, 0], [x + r, y + d - r, 90], [x + r, y + r, 180]])
      for (let i = 0; i <= 5; i++) ring.push([cx + r * Math.cos((a + i * 18) * R), cy + r * Math.sin((a + i * 18) * R)])
    return ring
  }
  const circle = (cx, cy, r, n = 28) =>
    Array.from({ length: n }, (_, i) => [cx + r * Math.cos((i / n) * 2 * Math.PI), cy + r * Math.sin((i / n) * 2 * Math.PI)])
  function hull(points) { // outline of a solid on screen
    const p = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1])
    const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    const half = (list) => list.reduce((h, q) => {
      while (h.length > 1 && cross(h[h.length - 2], h[h.length - 1], q) <= 0) h.pop()
      return h.push(q), h
    }, [])
    const lo = half(p), hi = half(p.reverse())
    return lo.slice(0, -1).concat(hi.slice(0, -1))
  }
  // A solid: a convex floor ring raised from z by h. Sides are shaded by the way they face;
  // the top is lightest, its front edges catch a glint, the outline is inked.
  // Returns { at, svg }: add details to svg (part.svg += ...) so they paint with the part.
  function prism(c, ring, z, h, tone = "part") {
    let sides = "", glint = ""
    const flat = []
    ring.forEach(([x1, y1], i) => {
      const [x2, y2] = ring[(i + 1) % ring.length]
      flat.push(project(c, [x1, y1, z]), project(c, [x1, y1, z + h]))
      const [u, t] = turn(c, y2 - y1, x1 - x2)
      if (t <= 0) return // faces away
      const lit = Math.round(50 - (50 * u) / Math.hypot(u, t))
      const fill = `color-mix(in srgb,var(--lit) ${lit}%,var(--shade))`
      sides += `<path d="${path(c, [[x1, y1, z], [x2, y2, z], [x2, y2, z + h], [x1, y1, z + h]])}" style="fill:${fill};stroke:${fill}"/>`
      glint += path(c, [[x1, y1, z + h], [x2, y2, z + h]], false)
    })
    const n = ring.length
    const mid = [ring.reduce((s, p) => s + p[0], 0) / n, ring.reduce((s, p) => s + p[1], 0) / n, z]
    const edge = "M" + hull(flat).map((p) => p.map((v) => v.toFixed(1)).join(" ")).join("L") + "Z"
    return {
      at: depth(c, mid),
      svg: `<g class="${tone}">${sides}<path class="top" d="${path(c, ring.map(([x, y]) => [x, y, z + h]))}"/>` +
        `<path class="glint" d="${glint}"/><path class="edge" d="${edge}"/></g>`,
    }
  }
  const box = (c, { x, y, z = 0, w, d, h, r = 0, tone }) => prism(c, rect(x, y, w, d, r), z, h, tone)
  const cyl = (c, { x, y, z = 0, r, h, tone }) => prism(c, circle(x, y, r), z, h, tone)
  // A soft shadow on the floor under a ring; drawn before everything.
  const shadow = (c, ring, z = 0) => ({ at: -1e9, svg: `<path class="shadow" d="${path(c, ring.map(([x, y]) => [x, y, z]))}"/>` })
  // A line between world points (a tick, a seam, a slot), as SVG.
  const line = (c, a, b, cls = "ink") => `<path class="${cls}" d="${path(c, [a, b], false)}"/>`
  // Parts back to front by depth; pass sort = false to keep your own order.
  const draw = (parts, sort = true) => (sort ? [...parts].sort((a, b) => a.at - b.at) : parts).map((p) => p.svg).join("")
  // Ease toward a target by elapsed time; tau is the time to close most of the gap.
  const follow = (v, target, dt, tau = 0.2) => v + (target - v) * (1 - Math.exp(-dt / tau))
  const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches
  // Call tick(dt) each frame while el is on screen, until it returns true; returns wake().
  function animate(el, tick) {
    let frame = 0, last = 0, seen = false
    const step = (now) => {
      const dt = last ? Math.min((now - last) / 1000, 1 / 30) : 1 / 60
      last = now
      frame = !tick(dt) && seen ? requestAnimationFrame(step) : 0
    }
    const wake = () => { if (!frame && seen) { last = 0; frame = requestAnimationFrame(step) } }
    new IntersectionObserver((e) => { seen = e[e.length - 1].isIntersecting; if (seen) wake() }, { rootMargin: "120px 0px" }).observe(el)
    return wake
  }
  return { camera, fit, project, depth, path, rect, circle, prism, box, cyl, shadow, line, draw, follow, still, animate }
})()
```
