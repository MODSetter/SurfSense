# The figure kit

Put `<script data-kit="fig"></script>` before your own script and `surfsense_save_page` writes the kit there. Do not copy the kit into the page. Everything is on `Fig`. The code is `kit/fig.js` in this skill's folder.

World points are `[x, y, z]`: x and y on the floor, z up, in units of about one pixel. Screen points are `[x, y]` in the SVG's `viewBox`.

## Camera

| Call | Does |
|---|---|
| `Fig.fit(points, width, height, { pad, azimuth, elevation })` | A camera that fits every world point in the viewBox. Pass the corners of the base and the tallest point. Defaults: `pad` 24, `azimuth` 45, `elevation` 30. |
| `Fig.camera({ azimuth, elevation, scale, origin })` | A camera by hand. |
| `Fig.project(cam, point)` | World to screen. |
| `Fig.depth(cam, point)` | Larger is nearer the viewer. |

## Solids

Each returns a solid: its visible faces and its depth.

| Call | Draws |
|---|---|
| `Fig.box(cam, { x, y, z, w, d, h, tone })` | A box from the floor corner `(x, y)` at height `z`, `w` along x, `d` along y, `h` up. |
| `Fig.cylinder(cam, { cx, cy, z, r, h, steps, tone })` | A round post, knob, foot or disc. |
| `Fig.prism(cam, ring, z, h, { tone })` | Any floor outline, counter-clockwise points `[x, y]`, raised by `h`. Convex outlines only. |
| `Fig.line(cam, from, to)` | A straight line between world points, as a path `d`. |
| `Fig.svg(solids, { sort })` | The solids as SVG markup, back to front. `sort: false` keeps your order. |
| `Fig.css` | Default colours; put it in a `<style>` and add class `fig` to the `<svg>`. |

Sides are shaded by the way they face; tops are lightest. Colours come from custom properties: `--fig-top`, `--fig-lit`, `--fig-shade` and `--fig-edge` on `.fig`. `Fig.css` sets light neutral ones; set your own from the page's palette, keeping the edges in contrast with the faces. A solid's `tone` puts its faces in a group with class `fig-<tone>`, which can set its own: `.fig-accent { --fig-top: …; --fig-lit: …; --fig-shade: …; }` for the subject.

## Motion

| Call | Does |
|---|---|
| `Fig.animate(element, tick)` | Calls `tick(dt, still)` each frame while `element` is on screen, until `tick` returns `true`. `dt` is seconds, clamped to 1/30. `still` is true under reduced motion: jump to the end state. Returns `wake()`: call it after input changes a target. |
| `Fig.follow(value, target, dt, tau)` | Eases toward the target; `tau` 0.1 to 0.3 s. |
| `Fig.spring(state, target, dt, stiffness, damping)` | A spring on `{ at, rate }`; returns `true` once settled. |
| `Fig.reducedMotion()` | Whether the reader asked for less motion. |

## Example: a carriage on a rail

```html
<figure class="card">
  <svg id="rig" class="fig" viewBox="0 0 640 360" tabindex="0" role="slider"
       aria-label="Carriage on a rail: the arrow keys move it between stops"
       aria-valuemin="1" aria-valuemax="3" aria-valuenow="1"
       aria-valuetext="stop 1 of 3"></svg>
  <figcaption>
    <span>Click the figure, then use the arrow keys</span>
    <span id="readout" role="status">stop 1 of 3</span>
  </figcaption>
</figure>
<script data-kit="fig"></script>
<script>
  document.head.insertAdjacentHTML("beforeend", `<style>${Fig.css}
    /* The subject in tints of the page's own --accent. */
    .fig-accent { --fig-top: color-mix(in srgb, var(--accent) 35%, white);
      --fig-lit: color-mix(in srgb, var(--accent) 70%, white); --fig-shade: var(--accent); }</style>`)
  const rig = document.getElementById("rig")
  const readout = document.getElementById("readout")
  const stops = [40, 160, 280]
  const cam = Fig.fit([[0, 0, 0], [360, 0, 0], [360, 80, 0], [0, 80, 0], [0, 0, 70]], 640, 360)
  let target = 0
  let x = stops[0]

  function draw() {
    const base = Fig.box(cam, { x: 0, y: 0, w: 360, d: 80, h: 14 })
    const rail = Fig.box(cam, { x: 10, y: 34, z: 14, w: 340, d: 12, h: 6 })
    const carriage = Fig.box(cam, { x, y: 22, z: 20, w: 40, d: 36, h: 24, tone: "accent" })
    const feet = [[12, 12], [348, 12], [12, 68], [348, 68]].map(([cx, cy]) =>
      Fig.cylinder(cam, { cx, cy, z: -6, r: 6, h: 6 }))
    rig.innerHTML = Fig.svg([...feet, base, rail]) + Fig.svg([carriage])
  }

  const wake = Fig.animate(rig, (dt, still) => {
    x = still ? stops[target] : Fig.follow(x, stops[target], dt, 0.25)
    if (Math.abs(x - stops[target]) < 0.1) x = stops[target]
    draw()
    return x === stops[target]
  })

  rig.addEventListener("keydown", (event) => {
    const moves = { ArrowRight: target + 1, ArrowLeft: target - 1, Home: 0, End: stops.length - 1 }
    if (!(event.key in moves)) return
    event.preventDefault()
    target = Math.max(0, Math.min(stops.length - 1, moves[event.key]))
    const said = `stop ${target + 1} of ${stops.length}`
    readout.textContent = said
    rig.setAttribute("aria-valuenow", String(target + 1))
    rig.setAttribute("aria-valuetext", said)
    wake()
  })
  draw()
</script>
```
