// SurfSense's figure kit: isometric solids drawn as SVG, the small parts that make
// them look made, and calm motion. surfsense_save_page writes this file into a page
// that asks for the "fig" kit, so the page itself stays short. Everything is on `Fig`.
const Fig = (() => {
  const RAD = Math.PI / 180
  // True isometric: the three axes meet at 120 degrees on screen.
  const ISO_ELEVATION = 35.264

  // ---- Camera ---------------------------------------------------------------

  // Looks down at the floor (x, y) from `elevation` degrees, turned `azimuth`
  // degrees about the vertical (z). `scale` is screen px per world unit.
  function camera({ azimuth = 45, elevation = ISO_ELEVATION, scale = 1, origin = [0, 0] } = {}) {
    const a = azimuth * RAD
    const e = elevation * RAD
    return {
      azimuth, elevation, scale, origin,
      cosA: Math.cos(a), sinA: Math.sin(a), cosE: Math.cos(e), sinE: Math.sin(e),
    }
  }

  // A floor direction in the camera's frame: [across, toward the viewer].
  function turn(cam, x, y) {
    return [x * cam.cosA - y * cam.sinA, x * cam.sinA + y * cam.cosA]
  }

  function project(cam, [x, y, z]) {
    const [across, toward] = turn(cam, x, y)
    return [
      cam.origin[0] + across * cam.scale,
      cam.origin[1] + (toward * cam.sinE - z * cam.cosE) * cam.scale,
    ]
  }

  // Larger is nearer the viewer: paint in ascending order.
  function depth(cam, [x, y, z]) {
    const [, toward] = turn(cam, x, y)
    return toward * cam.cosE + z * cam.sinE
  }

  // A camera that fits these world points in a width x height viewBox. Pass the
  // subject's extremes, not empty floor, so the subject fills the frame.
  function fit(points, width, height, { pad = 24, azimuth = 45, elevation = ISO_ELEVATION } = {}) {
    const unit = camera({ azimuth, elevation })
    const flat = points.map((p) => project(unit, p))
    const xs = flat.map((p) => p[0])
    const ys = flat.map((p) => p[1])
    const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
    const scale = Math.min((width - 2 * pad) / (maxX - minX || 1), (height - 2 * pad) / (maxY - minY || 1))
    const origin = [
      (width - (maxX - minX) * scale) / 2 - minX * scale,
      (height - (maxY - minY) * scale) / 2 - minY * scale,
    ]
    return camera({ azimuth, elevation, scale, origin })
  }

  // The eight corners of a box, for fit().
  function corners({ x, y, z = 0, w, d, h }) {
    const out = []
    for (const px of [x, x + w]) for (const py of [y, y + d]) for (const pz of [z, z + h]) out.push([px, py, pz])
    return out
  }

  // ---- Outlines on the floor ------------------------------------------------

  const round = (n) => Math.round(n * 10) / 10
  const pt = (cam, p) => project(cam, p).map(round).join(" ")
  const closed = (cam, points3) => "M" + points3.map((p) => pt(cam, p)).join("L") + "Z"
  const open = (cam, points3) => "M" + points3.map((p) => pt(cam, p)).join("L")

  // A rounded rectangle's outline, counter-clockwise; r 0 gives a plain one.
  function roundedRing({ x, y, w, d, r = 0 }, steps = 6) {
    r = Math.max(0, Math.min(r, w / 2, d / 2))
    if (r === 0) return [[x, y], [x + w, y], [x + w, y + d], [x, y + d]]
    const ring = []
    const arcs = [[x + w - r, y + r, -90], [x + w - r, y + d - r, 0], [x + r, y + d - r, 90], [x + r, y + r, 180]]
    for (const [cx, cy, start] of arcs) {
      for (let i = 0; i <= steps; i++) {
        const t = (start + (90 * i) / steps) * RAD
        ring.push([cx + r * Math.cos(t), cy + r * Math.sin(t)])
      }
    }
    return ring
  }

  function circleRing(cx, cy, r, steps = 36) {
    const ring = []
    for (let i = 0; i < steps; i++) {
      const t = (i / steps) * 2 * Math.PI
      ring.push([cx + r * Math.cos(t), cy + r * Math.sin(t)])
    }
    return ring
  }

  // The ring moved in toward its middle by `by` world units (convex rings).
  function inset(ring, by) {
    const cx = ring.reduce((s, p) => s + p[0], 0) / ring.length
    const cy = ring.reduce((s, p) => s + p[1], 0) / ring.length
    return ring.map(([x, y]) => {
      const dx = cx - x
      const dy = cy - y
      const len = Math.hypot(dx, dy) || 1
      const k = Math.min(by, len * 0.5) / len
      return [x + dx * k, y + dy * k]
    })
  }

  // The convex hull of screen points, for a solid's silhouette.
  function hull(points) {
    const p = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1])
    const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    const lower = []
    for (const q of p) {
      while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], q) <= 0) lower.pop()
      lower.push(q)
    }
    const upper = []
    for (let i = p.length - 1; i >= 0; i--) {
      const q = p[i]
      while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], q) <= 0) upper.pop()
      upper.push(q)
    }
    return lower.slice(0, -1).concat(upper.slice(0, -1))
  }

  // ---- Solids -----------------------------------------------------------------

  // How lit a side is, 0 to 1, from where its outward normal points on screen.
  function lightOf(cam, nx, ny) {
    const length = Math.hypot(nx, ny) || 1
    const [across] = turn(cam, nx / length, ny / length)
    return Math.max(0, Math.min(1, 0.5 - across / 2))
  }

  // A convex floor outline (counter-clockwise [x, y] points) raised from z by h.
  // Sides are shaded by the way they face, the top is lightest, the silhouette and
  // the top's rim are inked, and the top's front edges catch a glint.
  function prism(cam, ring, z, h, { tone = "solid", bevel = true } = {}) {
    const sides = []
    const front = []
    for (let i = 0; i < ring.length; i++) {
      const [x1, y1] = ring[i]
      const [x2, y2] = ring[(i + 1) % ring.length]
      const nx = y2 - y1
      const ny = x1 - x2
      if (turn(cam, nx, ny)[1] <= 0) continue // faces away
      front.push(i)
      sides.push({
        d: closed(cam, [[x1, y1, z], [x2, y2, z], [x2, y2, z + h], [x1, y1, z + h]]),
        light: lightOf(cam, nx, ny),
        at: depth(cam, [(x1 + x2) / 2, (y1 + y2) / 2, z]),
      })
    }
    sides.sort((a, b) => a.at - b.at)
    const top = ring.map(([x, y]) => [x, y, z + h])
    const flat = [...ring.map(([x, y]) => project(cam, [x, y, z])), ...top.map((p) => project(cam, p))]
    const silhouette = "M" + hull(flat).map((p) => p.map(round).join(" ")).join("L") + "Z"
    let glint = ""
    if (bevel && h > 0) {
      const edge = inset(ring, Math.min(1.4, h * 0.25))
      const runs = front.map((i) => [edge[i], edge[(i + 1) % edge.length]])
      glint = runs.map(([a, b]) => open(cam, [[...a, z + h], [...b, z + h]])).join("")
    }
    const cx = ring.reduce((s, p) => s + p[0], 0) / ring.length
    const cy = ring.reduce((s, p) => s + p[1], 0) / ring.length
    return {
      tone, sides, top: closed(cam, top), silhouette, glint, extra: [],
      depth: depth(cam, [cx, cy, z]), cam, ring, z, h,
    }
  }

  // A box from floor corner (x, y) at height z: w along x, d along y, h up; r rounds its corners.
  function box(cam, { x, y, z = 0, w, d, h, r = 0, tone, bevel }) {
    return prism(cam, roundedRing({ x, y, w, d, r }), z, h, { tone, bevel })
  }

  // A round post, foot, knob, puck or disc.
  function cylinder(cam, { cx, cy, z = 0, r, h, steps = 36, tone, bevel }) {
    const solid = prism(cam, circleRing(cx, cy, r, steps), z, h, { tone, bevel })
    return Object.assign(solid, { round: true, cx, cy, r })
  }

  // A soft shadow on the floor under a footprint ({x, y, w, d, r} or {cx, cy, r}), drawn first.
  function shadow(cam, shape, { z = 0, spread = 4 } = {}) {
    const ring = "cx" in shape
      ? circleRing(shape.cx, shape.cy, shape.r + spread, 24)
      : roundedRing({ x: shape.x - spread, y: shape.y - spread, w: shape.w + 2 * spread, d: shape.d + 2 * spread, r: (shape.r || 0) + spread })
    return { depth: -Infinity, markup: `<path class="fig-sh" d="${closed(cam, ring.map(([x, y]) => [x, y, z]))}"/>` }
  }

  // ---- Small parts on a solid ------------------------------------------------
  // Each draws onto `solid` and paints with it, right after its faces. Returns the solid.

  const top = (solid) => solid.z + solid.h

  function ink(solid, markup) {
    solid.extra.push(markup)
    return solid
  }

  // Screw heads on the solid's top: tiny domes with a slot.
  function screws(cam, solid, points, { r = 2.2, z = top(solid) } = {}) {
    const marks = points.map(([x, y]) => {
      const head = closed(cam, circleRing(x, y, r, 12).map(([a, b]) => [a, b, z + 0.4]))
      const slot = open(cam, [[x - r * 0.7, y + r * 0.7, z + 0.5], [x + r * 0.7, y - r * 0.7, z + 0.5]])
      return `<path class="fig-screw" d="${head}"/><path class="fig-ink" d="${slot}"/>`
    })
    return ink(solid, marks.join(""))
  }

  // A grid of small holes or studs on the solid's top: a speaker, a vent, a keypad.
  function dots(cam, solid, { x, y, w, d, cols, rows, r = 1, z = top(solid) }) {
    const marks = []
    for (let i = 0; i < cols; i++) {
      for (let j = 0; j < rows; j++) {
        const cx = x + (cols === 1 ? w / 2 : (w * i) / (cols - 1))
        const cy = y + (rows === 1 ? d / 2 : (d * j) / (rows - 1))
        marks.push(closed(cam, circleRing(cx, cy, r, 8).map(([a, b]) => [a, b, z + 0.2])))
      }
    }
    return ink(solid, `<path class="fig-hole" d="${marks.join("")}"/>`)
  }

  // A ruler's ticks from `from` to `to` (world points), each `len` long along `dir`;
  // every `major`th tick is twice as long.
  function ticks(cam, solid, { from, to, count, major = 5, len = 3, dir = [0, 1, 0] }) {
    const marks = []
    for (let i = 0; i <= count; i++) {
      const t = i / count
      const p = from.map((f, k) => f + (to[k] - f) * t)
      const l = i % major === 0 ? len * 2 : len
      marks.push(open(cam, [p, p.map((v, k) => v + dir[k] * l)]))
    }
    return ink(solid, `<path class="fig-ink" d="${marks.join("")}"/>`)
  }

  // Draw on any flat face: `origin` is a world point on it, `u` the world direction
  // of its width and `v` of its height (unit vectors). `draw` gets a pen in face units.
  function onFace(cam, solid, origin, u, v, draw) {
    const at = (s, t) => [0, 1, 2].map((k) => origin[k] + s * u[k] + t * v[k])
    const o = project(cam, origin)
    const pu = project(cam, at(1, 0))
    const pv = project(cam, at(0, 1))
    // Text runs along u and up v; SVG's y runs down.
    const matrix = [pu[0] - o[0], pu[1] - o[1], -(pv[0] - o[0]), -(pv[1] - o[1])].map((n) => n.toFixed(4))
    const marks = []
    const pen = {
      line(s1, t1, s2, t2, cls = "fig-ink") {
        marks.push(`<path class="${cls}" d="${open(cam, [at(s1, t1), at(s2, t2)])}"/>`)
      },
      rect(s, t, w, h, cls = "fig-panel") {
        marks.push(`<path class="${cls}" d="${closed(cam, [at(s, t), at(s + w, t), at(s + w, t + h), at(s, t + h)])}"/>`)
      },
      slots(s, t, w, h, count, cls = "fig-hole") {
        const gap = h / (count * 2 - 1)
        for (let i = 0; i < count; i++) pen.rect(s, t + i * gap * 2, w, gap, cls)
      },
      dot(s, t, r = 1, cls = "fig-hole") {
        marks.push(`<path class="${cls}" d="${closed(cam, circleRing(0, 0, r, 10).map(([a, b]) => at(s + a, t + b)))}"/>`)
      },
      text(words, s, t, { size = 5, anchor = "start", cls = "fig-text" } = {}) {
        const [x, y] = project(cam, at(s, t))
        const safe = String(words).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c])
        marks.push(`<text class="${cls}" font-size="${size}" text-anchor="${anchor}" transform="matrix(${matrix.join(" ")} ${round(x)} ${round(y)})">${safe}</text>`)
      },
    }
    draw(pen)
    return ink(solid, marks.join(""))
  }

  // Fine grooves around a cylinder's visible side: a knob's grip.
  function knurl(cam, solid, { count = 36, from = 0.15, to = 0.85 } = {}) {
    const marks = []
    for (let i = 0; i < count; i++) {
      const t = (i / count) * 2 * Math.PI
      if (turn(cam, Math.cos(t), Math.sin(t))[1] <= 0.05) continue
      const x = solid.cx + solid.r * Math.cos(t)
      const y = solid.cy + solid.r * Math.sin(t)
      marks.push(open(cam, [[x, y, solid.z + solid.h * from], [x, y, solid.z + solid.h * to]]))
    }
    return ink(solid, `<path class="fig-ink" d="${marks.join("")}"/>`)
  }

  // A coil spring from world point `from` to `to`, as two halves so a rod can pass
  // through it: the back half paints before the rod and the front half after it.
  function coil(cam, { from, to, r, turns = 6 }) {
    const axis = to.map((v, k) => v - from[k])
    const length = Math.hypot(...axis) || 1
    const a = axis.map((v) => v / length)
    // Two directions across the axis.
    const seed = Math.abs(a[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0]
    const cross = (m, n) => [m[1] * n[2] - m[2] * n[1], m[2] * n[0] - m[0] * n[2], m[0] * n[1] - m[1] * n[0]]
    const unit = (m) => { const l = Math.hypot(...m) || 1; return m.map((v) => v / l) }
    const p = unit(cross(a, seed))
    const q = cross(a, p)
    const back = []
    const front = []
    const steps = Math.ceil(turns * 24)
    let run = null
    let side = null
    for (let i = 0; i <= steps; i++) {
      const t = (i / steps) * turns * 2 * Math.PI
      const centre = from.map((v, k) => v + axis[k] * (i / steps))
      const point = centre.map((v, k) => v + r * (Math.cos(t) * p[k] + Math.sin(t) * q[k]))
      const near = depth(cam, point) > depth(cam, centre)
      if (near !== side) {
        if (run) run.push(point)
        run = [point]
        ;(near ? front : back).push(run)
        side = near
      } else run.push(point)
    }
    const mid = depth(cam, from.map((v, k) => v + axis[k] / 2))
    const path = (runs, cls) => `<path class="${cls}" d="${runs.map((r) => open(cam, r)).join("")}"/>`
    return [
      { depth: mid - 0.5, markup: path(back, "fig-coil-back") },
      { depth: mid + 0.5, markup: path(front, "fig-coil") },
    ]
  }

  // A cable or rod along world points, drawn as a thick stroke at a depth you give.
  function wire(cam, points, { cls = "fig-wire", at = depth(cam, points[0]) } = {}) {
    return { depth: at, markup: `<path class="${cls}" d="${open(cam, points)}"/>` }
  }

  // ---- Output -----------------------------------------------------------------

  function solidMarkup(solid) {
    const faces = solid.sides.map((face) => {
      const shade = `color-mix(in srgb, var(--fig-lit) ${Math.round(face.light * 100)}%, var(--fig-shade))`
      // Fill the seam with the face's own colour: the silhouette carries the edge.
      return `<path d="${face.d}" style="fill:${shade};stroke:${shade}"/>`
    })
    return `<g class="fig-${solid.tone}">${faces.join("")}<path class="fig-top" d="${solid.top}"/>` +
      (solid.glint ? `<path class="fig-glint" d="${solid.glint}"/>` : "") +
      `<path class="fig-edge" d="${solid.silhouette}"/>${solid.extra.join("")}</g>`
  }

  // Solids, shadows, coils and wires as SVG markup, back to front. Arrays are
  // flattened; { sort: false } keeps your order.
  function svg(items, { sort = true } = {}) {
    const flat = items.flat(Infinity).filter(Boolean)
    const ordered = sort ? [...flat].sort((a, b) => a.depth - b.depth) : flat
    return ordered.map((item) => ("markup" in item ? item.markup : solidMarkup(item))).join("")
  }

  // Light neutrals as custom properties; a page sets its own from its palette
  // (pages are light only). A tone class sets its own: .fig-accent { --fig-top: … }
  const css = `
.fig { --fig-top:#f6f5f2; --fig-lit:#e1dfda; --fig-shade:#aeaba3; --fig-edge:#3f3d38;
  --fig-glint:#ffffff; --fig-ink:#4a4740; --fig-shadow:rgba(40,36,30,.22); --fig-hole:#3a3833; --fig-panel:#d7d4cc; }
.fig path { stroke-linejoin:round; stroke-linecap:round; }
.fig .fig-top { fill:var(--fig-top); stroke:var(--fig-edge); stroke-width:.6; }
.fig .fig-edge { fill:none; stroke:var(--fig-edge); stroke-width:1; }
.fig .fig-glint { fill:none; stroke:var(--fig-glint); stroke-width:1; opacity:.85; }
.fig .fig-ink { fill:none; stroke:var(--fig-ink); stroke-width:.6; }
.fig .fig-hole { fill:var(--fig-hole); stroke:none; }
.fig .fig-panel { fill:var(--fig-panel); stroke:var(--fig-edge); stroke-width:.5; }
.fig .fig-screw { fill:var(--fig-lit); stroke:var(--fig-edge); stroke-width:.5; }
.fig .fig-sh { fill:var(--fig-shadow); stroke:none; filter:blur(3px); }
.fig .fig-coil { fill:none; stroke:var(--fig-edge); stroke-width:1.6; }
.fig .fig-coil-back { fill:none; stroke:var(--fig-shade); stroke-width:1.2; }
.fig .fig-wire { fill:none; stroke:var(--fig-edge); stroke-width:2.4; }
.fig .fig-text { fill:var(--fig-ink); font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace; font-weight:600; letter-spacing:.04em; }`

  // ---- Motion ----------------------------------------------------------------

  const reducedMotion = () =>
    typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches

  // Move toward a target by elapsed time; tau is how long it takes to close most of the gap.
  function follow(value, target, dt, tau = 0.2) {
    return value + (target - value) * (1 - Math.exp(-dt / tau))
  }

  // A spring { at, rate } pulled toward target; returns true once it has settled there.
  function spring(state, target, dt, stiffness = 300, damping = 24) {
    const steps = Math.max(1, Math.ceil(dt * 240))
    const h = dt / steps
    for (let i = 0; i < steps; i++) {
      const force = stiffness * (target - state.at) - damping * state.rate
      state.rate += force * h
      state.at += state.rate * h
    }
    if (Math.abs(target - state.at) < 5e-4 && Math.abs(state.rate) < 5e-4) {
      state.at = target
      state.rate = 0
      return true
    }
    return false
  }

  // Run tick(dt, still) every frame while `element` is on screen, until tick returns true
  // (settled). `still` is true under reduced motion: jump to the end state. Returns wake(),
  // which starts it again after input changes a target.
  function animate(element, tick) {
    let frame = 0
    let last = 0
    let visible = false
    const step = (now) => {
      const dt = last ? Math.min((now - last) / 1000, 1 / 30) : 1 / 60
      last = now
      const settled = tick(dt, reducedMotion()) === true
      frame = visible && !settled ? requestAnimationFrame(step) : 0
    }
    const wake = () => {
      if (!frame && visible) {
        last = 0
        frame = requestAnimationFrame(step)
      }
    }
    if (typeof IntersectionObserver === "function") {
      new IntersectionObserver((entries) => {
        visible = entries[entries.length - 1].isIntersecting
        if (visible) wake()
      }, { rootMargin: "120px 0px" }).observe(element)
    } else {
      visible = true
      wake()
    }
    return wake
  }

  return {
    camera, project, depth, fit, corners, roundedRing, circleRing,
    prism, box, cylinder, shadow, screws, dots, ticks, onFace, knurl, coil, wire,
    line: (cam, from, to) => open(cam, [from, to]), svg, css,
    reducedMotion, follow, spring, animate,
  }
})()
