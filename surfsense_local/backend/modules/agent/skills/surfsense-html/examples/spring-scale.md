# Example: A spring scale

**Use it for:** One part sliding along a straight path as a number changes: a scale, a slider, a threshold, a pressure, a gauge, anything that moves in proportion to a value.

**Worth copying:**

- A base sized to the mechanism, with feet, corner screws, a ruler of ticks and a label plate.
- A spring drawn in back and front halves round its rod (`coil`), and how to paint them in order.
- Details added to the part they sit on: screws on the carriage, grip lines on the knob, slots on the anchor.
- A slider the keyboard drives, with the readout and `aria-valuetext` from one number.

The page is complete and works as it is: the `ISO` helper from `isometric.md`, then the figure's own code. Start from it, change the object to yours, and keep its structure: the card with a title, a hint and a live readout; the tones; the layers; the keyboard; reduced motion.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>How a spring scale measures force</title>
<style>
  :root {
    color-scheme: light;
    --bg: #f6f3ec; --surface: #fffdf8; --stage: #f8f5ee; --text: #1f1d19; --muted: #5d584e; --border: #e2dccf; --border-strong: #b9b09d; --accent: #b4461f;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text); font: 17px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  main { max-width: 860px; margin: 0 auto; padding: 40px 16px 56px; }
  h1 { font: 700 clamp(1.8rem, 5vw, 2.5rem)/1.15 "Iowan Old Style", "Palatino Linotype", Georgia, serif; margin: 0 0 8px; }
  .lede { color: var(--muted); margin: 0 0 24px; max-width: 64ch; }
  .card { margin: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 12px; }
  .card header { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding: 4px 6px 8px; font-size: .95rem; }
  .card header b { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; color: var(--accent); }
  .card footer { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; align-items: center; padding: 8px 6px 2px; color: var(--muted); font-size: .95rem; }
  .card footer output { font: 600 .95rem ui-monospace, "SF Mono", Menlo, Consolas, monospace; color: var(--text); }
  button { font: inherit; min-height: 44px; padding: 8px 14px; border-radius: 10px; border: 1.5px solid var(--border-strong); background: var(--surface); color: var(--text); cursor: pointer; }
  button:focus-visible, svg:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
  /* The figure: every colour is a custom property; a tone class sets a part's three. */
  svg.fig { display: block; width: 100%; height: auto; border-radius: 10px; background: var(--stage); }
  .fig { --edge: #3d3a34; }
  .fig .top { fill: var(--top); stroke: var(--edge); stroke-width: .6; }
  .fig .edge { fill: none; stroke: var(--edge); stroke-width: 1; }
  .fig .glint { fill: none; stroke: #fff; stroke-width: 1; opacity: .85; }
  .fig .ink { fill: none; stroke: var(--edge); stroke-width: .7; }
  .fig .slot { fill: none; stroke: #2a2824; stroke-width: 2.2; stroke-linecap: round; }
  .fig .shadow { fill: rgba(40, 34, 26, .2); filter: blur(4px); }
  .fig path { stroke-linejoin: round; }
  .plate { --top: #f3efe6; --lit: #e3ddd0; --shade: #b7ae9c; } .metal { --top: #eef1f4; --lit: #cfd5db; --shade: #7c8690; } .label { --top: #d9d3c4; --lit: #cfc8b7; --shade: #a59d8a; } .subject { --top: #f2c6b1; --lit: #dc7a52; --shade: #a3401b; } .fig .coil { fill: none; stroke: var(--edge); stroke-width: 1.6; } .fig .coil-back { fill: none; stroke: #9a9284; stroke-width: 1.2; }
  p { max-width: 64ch; }
</style>
</head>
<body>
<main>
  <h1>A spring scale turns a force into a distance</h1>
  <p class="lede">The spring stretches in proportion to the load, so a ruler beside the carriage reads newtons. This scale stretches 8 mm for every newton.</p>
  <figure class="card">
    <header><b>Spring scale</b><span>Click the figure, then use the arrow keys</span></header>
    <svg id="fig" class="fig" viewBox="0 0 720 400" tabindex="0" role="slider" aria-label="Spring scale: the arrow keys add or take away load" aria-valuemin="0" aria-valuemax="10" aria-valuenow="4" aria-valuetext="load 4 N, stretch 32 mm"></svg>
    <footer><span>0 to 10 N</span><output id="readout" role="status">load 4 N · stretch 32 mm</output></footer>
  </figure>
  <p>Doubling the load doubles the stretch: that straight line is Hooke’s law, and it is why the ruler’s marks are evenly spaced.</p>
</main>
<script>
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

const svg = document.getElementById("fig")
const readout = document.getElementById("readout")
const STIFFNESS = 8 // mm of stretch per newton: the readout and the drawing use the same number
const REST = -60 // the carriage's x with no load
const cam = ISO.fit(ISO.camera(), [[-170, -60, -6], [170, -60, -6], [170, 60, -6], [-170, 60, -6], [-170, -60, 64], [170, 60, 64]], 720, 400, 16)
let load = 4
let x = REST + load * STIFFNESS

// A coil spring between two points on the x axis, in a back and a front half so the rod can pass through.
function coil(x0, x1, y, z, r, turns) {
  const back = [], front = []
  let run = null, near = null
  for (let i = 0; i <= turns * 24; i++) {
    const t = (i / 24) * 2 * Math.PI
    const p = [x0 + ((x1 - x0) * i) / (turns * 24), y + r * Math.cos(t), z + r * Math.sin(t)]
    const n = ISO.depth(cam, p) > ISO.depth(cam, [p[0], y, z])
    if (n !== near) { if (run) run.push(p); run = [p]; (n ? front : back).push(run); near = n } else run.push(p)
  }
  const svgOf = (runs, cls) => runs.map((r) => `<path class="${cls}" d="${ISO.path(cam, r, false)}"/>`).join("")
  return [{ svg: svgOf(back, "coil-back") }, { svg: svgOf(front, "coil") }]
}

function scene() {
  const base = ISO.box(cam, { x: -170, y: -60, w: 340, d: 120, h: 10, r: 10, tone: "plate" })
  for (const [sx, sy] of [[-156, -46], [156, -46], [-156, 46], [156, 46]])
    base.svg += ISO.cyl(cam, { x: sx, y: sy, z: 10, r: 2.6, h: 0.8, tone: "metal" }).svg
  for (let i = 0; i <= 26; i++) {
    const tx = -130 + i * 10
    base.svg += ISO.line(cam, [tx, 34, 10], [tx, 34 + (i % 5 ? 3 : 6), 10])
  }
  base.svg += ISO.box(cam, { x: 64, y: 44, z: 10, w: 76, d: 10, h: 0.6, r: 1.5, tone: "label" }).svg
  const feet = [[-152, -42], [152, -42], [-152, 42], [152, 42]].map(([fx, fy]) => ISO.cyl(cam, { x: fx, y: fy, z: -6, r: 8, h: 6, tone: "metal" }))
  const rail = ISO.box(cam, { x: -140, y: -7, z: 10, w: 280, d: 14, h: 5, r: 2, tone: "metal" })
  const anchor = ISO.box(cam, { x: -150, y: -18, z: 10, w: 16, d: 36, h: 34, r: 3, tone: "plate" })
  for (let i = 0; i < 4; i++) anchor.svg += ISO.line(cam, [-134, -12, 18 + i * 6], [-134, 12, 18 + i * 6], "slot")
  const stop = ISO.box(cam, { x: 134, y: -18, z: 10, w: 16, d: 36, h: 24, r: 3, tone: "plate" })
  const rod = ISO.box(cam, { x: -134, y: -2, z: 26, w: x - 22 + 134, d: 4, h: 4, tone: "metal" })
  const [springBack, springFront] = coil(-134, x - 22, 0, 28, 9, 9)
  const carriage = ISO.box(cam, { x: x - 22, y: -22, z: 15, w: 44, d: 44, h: 26, r: 4, tone: "subject" })
  for (const [sx, sy] of [[-15, -15], [15, -15], [-15, 15], [15, 15]])
    carriage.svg += ISO.cyl(cam, { x: x + sx, y: sy, z: 41, r: 2.2, h: 0.6, tone: "metal" }).svg
  const knob = ISO.cyl(cam, { x, y: 0, z: 41, r: 9, h: 10, tone: "metal" })
  for (let a = 0; a < 360; a += 15) {
    const gx = x + 9 * Math.cos(a * Math.PI / 180), gy = 9 * Math.sin(a * Math.PI / 180)
    if (ISO.depth(cam, [gx, gy, 0]) > ISO.depth(cam, [x, 0, 0])) knob.svg += ISO.line(cam, [gx, gy, 43], [gx, gy, 49])
  }
  const pointer = ISO.box(cam, { x: x - 1.5, y: 22, z: 15, w: 3, d: 14, h: 2, tone: "subject" })
  // Back to front by hand: the spring's back half, the rod, then its front half.
  svg.innerHTML = ISO.draw([ISO.shadow(cam, ISO.rect(-176, -66, 352, 132, 14), -6)]) +
    ISO.draw([...feet, base, rail, anchor, stop, springBack, rod, springFront, carriage, knob, pointer], false)
}

const wake = ISO.animate(svg, (dt) => {
  const target = REST + load * STIFFNESS
  x = ISO.still() ? target : ISO.follow(x, target, dt, 0.25)
  if (Math.abs(x - target) < 0.05) x = target
  scene()
  return x === target
})

function setLoad(n) {
  load = Math.max(0, Math.min(10, n))
  const said = `load ${load} N · stretch ${load * STIFFNESS} mm`
  readout.textContent = said
  svg.setAttribute("aria-valuenow", String(load))
  svg.setAttribute("aria-valuetext", said)
  wake()
}
svg.addEventListener("keydown", (e) => {
  const to = { ArrowRight: load + 1, ArrowLeft: load - 1, Home: 0, End: 10 }[e.key]
  if (to === undefined) return
  e.preventDefault()
  setLoad(to)
})
scene()
</script>
</body>
</html>
```
