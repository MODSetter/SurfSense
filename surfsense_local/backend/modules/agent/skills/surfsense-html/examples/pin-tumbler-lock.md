# Example: A pin-tumbler lock

**Use it for:** Several parts that must all line up for something to happen: a match or a check, a key, a combination, a cache hit, an all-or-nothing condition.

**Worth copying:**

- A cut-away: a back wall and side frames so the inside shows, the moving parts painted in front.
- Many similar parts from one loop (five pin stacks), each easing to its own target.
- A state shown by a tone (the plug turns green) and by a part that moves (the bolt).
- Two inputs: the arrow keys and a button that swaps the key.

The page is complete and works as it is: the `ISO` helper from `isometric.md`, then the figure's own code. Start from it, change the object to yours, and keep its structure: the card with a title, a hint and a live readout; the tones; the layers; the keyboard; reduced motion.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>How a pin-tumbler lock checks a key</title>
<style>
  :root {
    color-scheme: light;
    --bg: #f4f1ea; --surface: #fffdf9; --stage: #f7f3eb; --text: #1d1c19; --muted: #5a564c; --border: #e0d9cb; --border-strong: #b5ab96; --accent: #0f6874;
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
  .plate { --top: #f3efe6; --lit: #e2dccf; --shade: #b5ac99; } .metal { --top: #eef1f4; --lit: #cdd3d9; --shade: #79838d; } .label { --top: #d9d3c4; --lit: #cfc8b7; --shade: #a59d8a; } .brass { --top: #f5e6bd; --lit: #dcbf72; --shade: #9a7a2e; } .subject { --top: #bfe0e3; --lit: #4fa3ad; --shade: #0f6874; } .open { --top: #c8ecd2; --lit: #4fb27a; --shade: #1f7a4a; } .pin { --top: #f6d2c4; --lit: #d9876a; --shade: #9a4426; } .driver { --top: #e4e7ea; --lit: #b7bec5; --shade: #6c757e; } .fig .coil { fill: none; stroke: #4a4740; stroke-width: 1.1; } .fig .shear { fill: none; stroke: #0f6874; stroke-width: 1.6; stroke-dasharray: 5 4; }
  p { max-width: 64ch; }
</style>
</head>
<body>
<main>
  <h1>A pin-tumbler lock turns only for the key that lines every pin up</h1>
  <p class="lede">Each chamber holds a key pin and a driver pin pushed down by a spring. The right key lifts every gap between them to the top of the plug, the shear line, and only then can the plug turn and draw the bolt back.</p>
  <figure class="card">
    <header><b>Pin-tumbler lock, cut away</b><span>Click the figure, then use the arrow keys</span></header>
    <svg id="fig" class="fig" viewBox="0 0 720 420" tabindex="0" role="slider" aria-label="Pin-tumbler lock: the arrow keys push the key in or pull it out" aria-valuemin="0" aria-valuemax="5" aria-valuenow="5"></svg>
    <footer><button type="button" id="which-key" aria-pressed="false">Try the wrong key</button><output id="readout" role="status"></output></footer>
  </figure>
  <p>A wrong key leaves some gaps above or below the shear line, so a pin bridges the plug and the housing and the plug cannot turn. The same idea checks a cache key: only a key that matches at every position lets the work be skipped.</p>
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
const keyButton = document.getElementById("which-key")
// Fit the lock and its base; a key pulled out slides off the left edge, as it would.
const cam = ISO.fit(ISO.camera(), [[-170, -45, 0], [130, -45, 0], [130, 45, 0], [-170, 45, 0], [-76, -24, 92]], 720, 420, 16)
const PINS = [-48, -24, 0, 24, 48] // x of each pin chamber
const SHEAR = 44 // the top of the plug: the plug turns only if every gap between pins is here
const RIGHT = [8, 4, 10, 6, 9] // the right key's cut height under each pin
const WRONG = [5, 9, 6, 10, 4]
const KEY_PINS = RIGHT.map((cut) => SHEAR - (24 + cut)) // cut so the right key lifts each to the shear line
const DRIVER = 16
let step = 0 // how far the key is in: 0 out, 5 fully in
let right = true
let tip = -60 // the key's tip x, easing toward its target
const lift = PINS.map(() => 22) // each key pin's bottom z, easing toward its target
let bolt = 0 // 0 thrown, 1 drawn back

const tipTarget = () => -60 + step * 24
// The bottom of a key pin: on the key's blade under it, or at the bottom of the keyway.
function pinTarget(i) {
  const local = PINS[i] - (tip - 120) // where along the 120-long blade the pin sits
  if (local < 0 || local > 120) return 22
  const cuts = right ? RIGHT : WRONG
  return 24 + cuts[Math.min(4, Math.floor(local / 24))]
}
const opened = () => step === 5 && PINS.every((_, i) => Math.abs(lift[i] + KEY_PINS[i] - SHEAR) < 0.3)

function helix(x, y, z0, z1, r, turns) {
  const pts = []
  for (let i = 0; i <= turns * 16; i++) {
    const t = (i / 16) * 2 * Math.PI
    pts.push([x + r * Math.cos(t), y + r * Math.sin(t), z0 + ((z1 - z0) * i) / (turns * 16)])
  }
  return `<path class="coil" d="${ISO.path(cam, pts, false)}"/>`
}

function scene() {
  const base = ISO.box(cam, { x: -170, y: -45, w: 300, d: 90, h: 10, r: 10, tone: "plate" })
  for (const [sx, sy] of [[-156, -31], [116, -31], [-156, 31], [116, 31]])
    base.svg += ISO.cyl(cam, { x: sx, y: sy, z: 10, r: 2.6, h: 0.8, tone: "metal" }).svg
  base.svg += ISO.box(cam, { x: 20, y: 30, z: 10, w: 84, d: 9, h: 0.6, r: 1.5, tone: "label" }).svg
  const back = ISO.box(cam, { x: -76, y: -24, z: 10, w: 152, d: 16, h: 82, r: 3, tone: "brass" })
  for (const px of PINS) back.svg += ISO.line(cam, [px - 7, -8, 50], [px - 7, -8, 88], "ink") + ISO.line(cam, [px + 7, -8, 50], [px + 7, -8, 88], "ink")
  const floor = ISO.box(cam, { x: -76, y: -8, z: 10, w: 152, d: 24, h: 10, tone: "brass" })
  const plug = ISO.box(cam, { x: -76, y: -8, z: 20, w: 152, d: 24, h: SHEAR - 20, tone: opened() ? "open" : "subject" })
  plug.svg += ISO.line(cam, [-76, 16, SHEAR], [76, 16, SHEAR], "shear")
  // The key: a bow to hold, then a blade cut to a different height under each pin.
  const key = [ISO.box(cam, { x: tip - 160, y: -2, z: 14, w: 40, d: 10, h: 36, r: 10, tone: "metal" })]
  const cuts = right ? RIGHT : WRONG
  cuts.forEach((cut, i) => key.push(ISO.box(cam, { x: tip - 120 + i * 24, y: 0, z: 24, w: 24, d: 6, h: cut, tone: "metal" })))
  const pins = []
  PINS.forEach((px, i) => {
    const top = lift[i] + KEY_PINS[i]
    pins.push(ISO.cyl(cam, { x: px, y: 4, z: lift[i], r: 6, h: KEY_PINS[i], tone: "pin" }))
    const driver = ISO.cyl(cam, { x: px, y: 4, z: top, r: 6, h: DRIVER, tone: "driver" })
    driver.svg += helix(px, 4, top + DRIVER, 88, 5, 5)
    pins.push(driver)
  })
  const leftWall = ISO.box(cam, { x: -76, y: -24, z: SHEAR, w: 8, d: 40, h: 48, tone: "brass" })
  const rightWall = ISO.box(cam, { x: 68, y: -24, z: 10, w: 8, d: 40, h: 82, tone: "brass" })
  // The bolt sticks out of the right side when thrown and slides in behind it when drawn.
  const throwBolt = ISO.box(cam, { x: 56 - 30 * bolt, y: -2, z: 28, w: 52, d: 12, h: 10, r: 2, tone: "metal" })
  svg.innerHTML = ISO.draw([ISO.shadow(cam, ISO.rect(-176, -51, 312, 102, 14), 0)]) +
    ISO.draw([base, back, floor, plug, ...key, ...pins, leftWall, throwBolt, rightWall], false)
}

function say() {
  const at = PINS.filter((_, i) => Math.abs(lift[i] + KEY_PINS[i] - SHEAR) < 0.3).length
  const said = `${right ? "right" : "wrong"} key · in ${step} of 5 · pins at the shear line ${step === 5 ? at : 0} of 5 · bolt ${opened() ? "drawn" : "thrown"}`
  readout.textContent = said
  svg.setAttribute("aria-valuenow", String(step))
  svg.setAttribute("aria-valuetext", said)
}

const wake = ISO.animate(svg, (dt) => {
  const still = ISO.still()
  tip = still ? tipTarget() : ISO.follow(tip, tipTarget(), dt, 0.18)
  if (Math.abs(tip - tipTarget()) < 0.1) tip = tipTarget()
  let moving = tip !== tipTarget()
  PINS.forEach((_, i) => {
    const t = pinTarget(i)
    lift[i] = still ? t : ISO.follow(lift[i], t, dt, 0.08)
    if (Math.abs(lift[i] - t) < 0.05) lift[i] = t
    moving ||= lift[i] !== t
  })
  const b = opened() ? 1 : 0
  bolt = still ? b : ISO.follow(bolt, b, dt, 0.2)
  if (Math.abs(bolt - b) < 0.005) bolt = b
  scene()
  if (!moving && bolt === b) say()
  return !moving && bolt === b
})

svg.addEventListener("keydown", (e) => {
  const to = { ArrowRight: step + 1, ArrowLeft: step - 1, Home: 0, End: 5 }[e.key]
  if (to === undefined) return
  e.preventDefault()
  step = Math.max(0, Math.min(5, to))
  wake()
})
keyButton.addEventListener("click", () => {
  right = !right
  step = 0
  keyButton.setAttribute("aria-pressed", String(!right))
  keyButton.textContent = right ? "Try the wrong key" : "Use the right key"
  wake()
})
step = 5
tip = tipTarget()
PINS.forEach((_, i) => (lift[i] = pinTarget(i)))
bolt = opened() ? 1 : 0
scene()
say()
</script>
</body>
</html>
```
