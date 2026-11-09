# Example: A conveyor with three workers

**Use it for:** Things flowing through stages: a queue, a pipeline, workers or servers, a request passing through steps, throughput and waiting.

**Worth copying:**

- Painting in layers: the base, then the long belt, then what stands on it sorted, so the belt never covers a parcel.
- Several moving things with their own state, handed to stations in order.
- Lights and progress bars as small parts on each station.
- A button and the Enter key adding work, and a loop that stops once everything has settled.

The page is complete and works as it is: the `ISO` helper from `isometric.md`, then the figure's own code. Start from it, change the object to yours, and keep its structure: the card with a title, a hint and a live readout; the tones; the layers; the keyboard; reduced motion.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>How a job queue shares work between workers</title>
<style>
  :root {
    color-scheme: light;
    --bg: #f3f2ee; --surface: #fefdfb; --stage: #f6f5f1; --text: #1c1d1f; --muted: #575a5f; --border: #dddbd4; --border-strong: #ada99d; --accent: #3d5bb8;
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
  .plate { --top: #f2f0ea; --lit: #e0ddd5; --shade: #b1ada2; } .metal { --top: #edf0f3; --lit: #cbd1d7; --shade: #78828c; } .belt { --top: #4b4f56; --lit: #3b3f45; --shade: #25282c; } .station { --top: #f4f1ea; --lit: #dedad0; --shade: #a8a397; } .track { --top: #d8d5cc; --lit: #cbc7bc; --shade: #9f9a8e; } .subject { --top: #b9c7f0; --lit: #6680cf; --shade: #3d5bb8; } .parcel { --top: #ecd3a8; --lit: #d3aa6a; --shade: #95703a; } .free { --top: #bfe8cc; --lit: #4caf73; --shade: #1f7a46; } .busy { --top: #f6d39a; --lit: #e3a33c; --shade: #a8671a; } .fig .stripe { fill: none; stroke: #6b7078; stroke-width: 1.2; } .fig .tape { fill: none; stroke: #8a6530; stroke-width: 2; }
  p { max-width: 64ch; }
</style>
</head>
<body>
<main>
  <h1>A job queue keeps every worker busy and the rest of the work waiting in line</h1>
  <p class="lede">Parcels arrive on a belt. Each goes to the first free station; when all three are busy, the rest wait at the head of the belt, in the order they came.</p>
  <figure class="card">
    <header><b>Conveyor and three workers</b><span>Add parcels, or focus the figure and press Enter</span></header>
    <svg id="fig" class="fig" viewBox="0 0 720 420" tabindex="0" role="button" aria-label="Conveyor and three workers: press Enter to add four parcels"></svg>
    <footer><button type="button" id="add">Add 4 parcels</button><output id="readout" role="status">waiting 4 · working 0 of 3 · done 0</output></footer>
  </figure>
  <p>Adding a fourth worker would shorten the line; making each job faster would too. A real queue does the same with messages and processes instead of parcels and people.</p>
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
const addButton = document.getElementById("add")
const cam = ISO.fit(ISO.camera(), [[-190, -80, 0], [170, -80, 0], [170, 60, 0], [-190, 60, 0], [-60, -64, 70]], 720, 420, 16)
const STATIONS = [-50, 30, 110] // x of each worker's station, behind the belt
const HEAD = -104 // where the first waiting parcel stops; the line grows to the left
const GAP = 26
const DESK = -56 // y of the desks, behind the belt
const WORK = 1.6 // seconds a worker spends on one parcel
const SPEED = 90 // belt speed, world units a second
const stations = STATIONS.map(() => ({ parcel: null, left: 0 }))
let parcels = [] // { x, y, station, phase: "belt" | "in" }
let belt = 0 // the belt's stripes move with it
let done = 0
let next = 1

function add(count) {
  const waiting = parcels.filter((p) => p.station === null).length
  for (let i = 0; i < count; i++) parcels.push({ id: next++, x: HEAD - GAP * (waiting + i), y: 0, station: null, phase: "belt" })
  wake()
}

function scene() {
  const base = ISO.box(cam, { x: -190, y: -80, w: 360, d: 140, h: 8, r: 10, tone: "plate" })
  for (const [sx, sy] of [[-176, -66], [156, -66], [-176, 46], [156, 46]])
    base.svg += ISO.cyl(cam, { x: sx, y: sy, z: 8, r: 2.6, h: 0.8, tone: "metal" }).svg
  const legs = [-160, 140].flatMap((lx) => [-18, 14].map((ly) => ISO.box(cam, { x: lx, y: ly, z: 8, w: 6, d: 4, h: 12, tone: "metal" })))
  const frame = ISO.box(cam, { x: -176, y: -22, z: 20, w: 336, d: 44, h: 6, r: 3, tone: "metal" })
  const surface = ISO.box(cam, { x: -170, y: -18, z: 26, w: 324, d: 36, h: 2, tone: "belt" })
  for (let sx = -170 + (belt % 18); sx < 154; sx += 18) surface.svg += ISO.line(cam, [sx, -18, 28], [sx, 18, 28], "stripe")
  const parts = [] // desks, lights and parcels: sorted among themselves by depth
  STATIONS.forEach((sx, i) => {
    const s = stations[i]
    const desk = ISO.box(cam, { x: sx - 26, y: -76, z: 8, w: 52, d: 40, h: 34, r: 4, tone: "station" })
    for (let k = 0; k < 3; k++) desk.svg += ISO.line(cam, [sx - 16 + k * 8, -36, 16], [sx - 16 + k * 8, -36, 30], "slot")
    // A progress bar on the desk, and a light that is green when the worker is free.
    desk.svg += ISO.box(cam, { x: sx - 18, y: -46, z: 42, w: 36, d: 5, h: 1, tone: "track" }).svg
    if (s.parcel) desk.svg += ISO.box(cam, { x: sx - 18, y: -46, z: 42, w: 36 * (1 - s.left / WORK), d: 5, h: 1.6, tone: "subject" }).svg
    parts.push(desk, ISO.cyl(cam, { x: sx + 16, y: -64, z: 42, r: 5, h: 6, tone: s.parcel ? "busy" : "free" }))
  })
  for (const p of parcels) {
    const z = 28 + 14 * (p.y / DESK) // rises from the belt onto the desk as it moves back
    const crate = ISO.box(cam, { x: p.x - 11, y: p.y - 11, z, w: 22, d: 22, h: 16, r: 2, tone: "parcel" })
    crate.svg += ISO.line(cam, [p.x - 11, p.y + 11, z + 8], [p.x + 11, p.y + 11, z + 8], "tape")
    parts.push(crate)
  }
  // In layers: a long belt's middle is nearer than a parcel on its far end, so depth alone would
  // paint the belt over the parcel. The base, then the belt, then what stands on them.
  svg.innerHTML = ISO.draw([ISO.shadow(cam, ISO.rect(-196, -86, 372, 152, 14), 0)]) +
    ISO.draw([base]) + ISO.draw([...legs, frame, surface], false) + ISO.draw(parts)
}

function say() {
  const waiting = parcels.filter((p) => p.station === null).length
  const busy = stations.filter((s) => s.parcel).length
  readout.textContent = `waiting ${waiting} · working ${busy} of 3 · done ${done}`
}

const wake = ISO.animate(svg, (dt) => {
  if (ISO.still()) dt = 5 // under reduced motion, show where things settle
  let moving = false
  for (const [i, s] of stations.entries()) {
    if (!s.parcel) continue
    s.left -= dt
    if (s.left <= 0) {
      parcels = parcels.filter((p) => p !== s.parcel)
      s.parcel = null
      done++
    }
  }
  // Hand the first waiting parcels to free workers, in order.
  for (const p of parcels.filter((q) => q.station === null)) {
    const free = stations.findIndex((s, i) => !s.parcel && !parcels.some((q) => q.station === i))
    if (free < 0) break
    p.station = free
  }
  let place = 0
  for (const p of parcels) {
    if (p.phase === "in") continue
    if (p.station === null) {
      // Waiting: close up behind the parcel ahead.
      const target = HEAD - GAP * place++
      if (p.x < target) { p.x = Math.min(target, p.x + SPEED * dt); moving = true }
      continue
    }
    // Assigned: ride to the station, then slide back onto its desk.
    const target = STATIONS[p.station]
    if (p.x < target) p.x = Math.min(target, p.x + SPEED * dt)
    else p.y = Math.max(DESK, p.y - SPEED * dt)
    if (p.y <= DESK) { p.phase = "in"; stations[p.station].parcel = p; stations[p.station].left = WORK }
    moving = true
  }
  if (moving || stations.some((s) => s.parcel)) belt += SPEED * dt
  scene()
  say()
  return !moving && !stations.some((s) => s.parcel)
})

addButton.addEventListener("click", () => add(4))
svg.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return
  e.preventDefault()
  add(4)
})
add(4)
</script>
</body>
</html>
```
