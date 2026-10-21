// SurfSense's figure kit: isometric solids drawn as SVG, and calm motion.
// surfsense_save_page writes this file into a page that asks for the "fig" kit,
// so the page itself stays short. Everything is on `Fig`.
const Fig = (() => {
  const RAD = Math.PI / 180

  // A camera looks down at the floor (x, y) from `elevation` degrees, turned
  // `azimuth` degrees about the vertical (z). `scale` is screen px per world unit.
  function camera({ azimuth = 45, elevation = 30, scale = 1, origin = [0, 0] } = {}) {
    const a = azimuth * RAD
    const e = elevation * RAD
    return {
      azimuth, elevation, scale, origin,
      cosA: Math.cos(a), sinA: Math.sin(a), cosE: Math.cos(e), sinE: Math.sin(e),
    }
  }

  // A floor direction turned into the camera's frame: [across, toward the viewer].
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

  // A camera that fits every point inside a width x height viewBox.
  function fit(points, width, height, { pad = 24, azimuth = 45, elevation = 30 } = {}) {
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

  const round = (n) => Math.round(n * 10) / 10
  function pathOf(cam, points3) {
    return "M" + points3.map((p) => project(cam, p).map(round).join(" ")).join("L") + "Z"
  }

  // How lit a side is, 0 (darkest) to 1, from where its outward normal points on screen.
  function lightOf(cam, nx, ny) {
    const length = Math.hypot(nx, ny) || 1
    const [across] = turn(cam, nx / length, ny / length)
    return Math.max(0, Math.min(1, 0.5 - across / 2))
  }

  // A floor outline (counter-clockwise points [x, y]) raised from z by h.
  // Returns faces to paint, back to front, and the solid's depth for ordering solids.
  function prism(cam, ring, z, h, { tone = "solid" } = {}) {
    const faces = []
    for (let i = 0; i < ring.length; i++) {
      const [x1, y1] = ring[i]
      const [x2, y2] = ring[(i + 1) % ring.length]
      const nx = y2 - y1
      const ny = x1 - x2
      const [, toward] = turn(cam, nx, ny)
      if (toward <= 0) continue // faces away from the viewer
      const corners = [[x1, y1, z], [x2, y2, z], [x2, y2, z + h], [x1, y1, z + h]]
      const mid = [(x1 + x2) / 2, (y1 + y2) / 2, z]
      faces.push({ d: pathOf(cam, corners), light: lightOf(cam, nx, ny), at: depth(cam, mid) })
    }
    faces.sort((a, b) => a.at - b.at)
    const top = ring.map(([x, y]) => [x, y, z + h])
    faces.push({ d: pathOf(cam, top), light: 1, top: true })
    const cx = ring.reduce((s, p) => s + p[0], 0) / ring.length
    const cy = ring.reduce((s, p) => s + p[1], 0) / ring.length
    return { faces, depth: depth(cam, [cx, cy, z]), tone }
  }

  function box(cam, { x, y, z = 0, w, d, h, tone }) {
    const ring = [[x, y], [x + w, y], [x + w, y + d], [x, y + d]]
    return prism(cam, ring, z, h, { tone })
  }

  function cylinder(cam, { cx, cy, z = 0, r, h, steps = 36, tone }) {
    const ring = []
    for (let i = 0; i < steps; i++) {
      const t = (i / steps) * 2 * Math.PI
      ring.push([cx + r * Math.cos(t), cy + r * Math.sin(t)])
    }
    return { ...prism(cam, ring, z, h, { tone }), round: true }
  }

  // A straight line in the world, as a path.
  function line(cam, from, to) {
    return "M" + project(cam, from).map(round).join(" ") + "L" + project(cam, to).map(round).join(" ")
  }

  // Solids as SVG markup, nearest last. Pass { sort: false } to keep your own order.
  function svg(solids, { sort = true } = {}) {
    const ordered = sort ? [...solids].sort((a, b) => a.depth - b.depth) : solids
    return ordered.map((solid) => {
      const tone = solid.tone || "solid"
      return `<g class="fig-${tone}">` + solid.faces.map((face) => {
        const shade = face.top ? "var(--fig-top)" :
          `color-mix(in srgb, var(--fig-lit) ${Math.round(face.light * 100)}%, var(--fig-shade))`
        // A round side's faces touch; filling the seam with the face's own colour hides it.
        const seam = solid.round && !face.top ? `stroke:${shade};stroke-width:.6` : "stroke:var(--fig-edge)"
        return `<path d="${face.d}" style="fill:${shade};${seam}"/>`
      }).join("") + "</g>"
    }).join("")
  }

  // Colours as custom properties, so a figure follows the page's light and dark scheme.
  // A tone class sets its own: .fig-accent { --fig-top: ...; --fig-lit: ...; --fig-shade: ... }
  const css = `
.fig { --fig-top:#f4f4f2; --fig-lit:#dcdcd8; --fig-shade:#a9a9a3; --fig-edge:#55554f; }
.fig path { stroke-width:.75; stroke-linejoin:round; }
@media (prefers-color-scheme: dark) {
  .fig { --fig-top:#3a3a37; --fig-lit:#2d2d2a; --fig-shade:#1c1c1a; --fig-edge:#8a8a84; }
}`

  // --- Motion -------------------------------------------------------------

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
    let settled = false
    const step = (now) => {
      const dt = last ? Math.min((now - last) / 1000, 1 / 30) : 1 / 60
      last = now
      settled = tick(dt, reducedMotion()) === true
      frame = visible && !settled ? requestAnimationFrame(step) : 0
    }
    const wake = () => {
      settled = false
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

  return { camera, project, depth, fit, prism, box, cylinder, line, svg, css,
    reducedMotion, follow, spring, animate }
})()
