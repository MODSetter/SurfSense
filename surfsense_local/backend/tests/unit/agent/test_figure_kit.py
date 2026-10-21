"""SurfSense's figure kit, run as a page would run it: a plain script defining `Fig`."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from modules.agent.opencode_config import skills_folder

pytestmark = pytest.mark.unit

KIT = skills_folder() / "surfsense-html" / "kit" / "fig.js"
NODE = shutil.which("node")


def _run(script: str) -> object:
    """Evaluate the kit, then `script`, in a bare context; the script's last value comes back as JSON."""
    if NODE is None:
        pytest.skip("node is not installed")
    program = (
        "const vm = require('vm');"
        "const context = vm.createContext({});"
        f"new vm.Script(require('fs').readFileSync({json.dumps(str(KIT))}, 'utf8')"
        " + ';globalThis.Fig = Fig;').runInContext(context);"
        f"const out = new vm.Script({json.dumps(script)}).runInContext(context);"
        "process.stdout.write(JSON.stringify(out));"
    )
    done = subprocess.run(
        [NODE, "-e", program], capture_output=True, text=True, timeout=20, check=True
    )
    return json.loads(done.stdout)


def test_it_runs_as_a_plain_script_without_eval_or_the_network() -> None:
    """The page's policy allows inline script only: no eval, no import, no fetch."""
    code = KIT.read_text(encoding="utf-8")
    for forbidden in (
        "eval(",
        "new Function",
        "import ",
        "require(",
        "fetch(",
        "</script",
    ):
        assert forbidden not in code
    names = _run("Object.keys(Fig).sort()")
    for name in (
        "fit",
        "box",
        "cylinder",
        "shadow",
        "screws",
        "onFace",
        "coil",
        "svg",
        "animate",
    ):
        assert name in names


def test_the_default_camera_is_true_isometric() -> None:
    """The three axes come out the same length on screen, as in an isometric drawing."""
    lengths = _run(
        "const cam = Fig.camera({ scale: 1 });"
        "const o = Fig.project(cam, [0, 0, 0]);"
        "[[1,0,0],[0,1,0],[0,0,1]].map((p) => {"
        "  const s = Fig.project(cam, p); return Math.hypot(s[0]-o[0], s[1]-o[1]) })"
    )
    assert max(lengths) - min(lengths) < 1e-3


def test_fit_puts_every_point_inside_the_view_box() -> None:
    """The figure fills the frame without spilling out of it."""
    inside = _run(
        "const pts = Fig.corners({ x: -170, y: -60, z: -6, w: 340, d: 120, h: 70 });"
        "const cam = Fig.fit(pts, 720, 420, { pad: 16 });"
        "pts.map((p) => Fig.project(cam, p)).every(([x, y]) => x >= 15.9 && x <= 704.1 && y >= 15.9 && y <= 404.1)"
    )
    assert inside is True


def test_a_box_shows_two_sides_a_top_a_silhouette_and_a_glint() -> None:
    """Only the sides facing the viewer are drawn; bevel false leaves the glint off."""
    shown = _run(
        "const cam = Fig.camera();"
        "const b = Fig.box(cam, { x: 0, y: 0, w: 40, d: 30, h: 10 });"
        "const flat = Fig.box(cam, { x: 0, y: 0, w: 40, d: 30, h: 10, bevel: false });"
        "[b.sides.length, b.top.endsWith('Z'), b.silhouette.endsWith('Z'), b.glint.length > 0, flat.glint]"
    )
    assert shown == [2, True, True, True, ""]


def test_rounded_corners_add_points_to_the_outline() -> None:
    """A rounded box is a ring of arcs; r 0 is four corners."""
    counts = _run(
        "[Fig.roundedRing({ x: 0, y: 0, w: 40, d: 30 }).length,"
        " Fig.roundedRing({ x: 0, y: 0, w: 40, d: 30, r: 5 }).length]"
    )
    assert counts == [4, 28]


def test_small_parts_paint_with_their_solid_after_its_faces() -> None:
    """Screws, ticks and a face's text go inside the solid's group, after its edge."""
    markup = _run(
        "const cam = Fig.camera();"
        "const b = Fig.box(cam, { x: 0, y: 0, w: 100, d: 60, h: 10 });"
        "Fig.screws(cam, b, [[8, 8]]);"
        "Fig.ticks(cam, b, { from: [10, 50, 10], to: [90, 50, 10], count: 8 });"
        "Fig.onFace(cam, b, [20, 55, 10.1], [1, 0, 0], [0, -1, 0], (pen) => pen.text('A < B & C', 0, 0));"
        "Fig.svg([b])"
    )
    edge = markup.index('class="fig-edge"')
    assert markup.index('class="fig-screw"') > edge
    assert markup.index('class="fig-text"') > edge
    assert "A &lt; B &amp; C" in markup
    assert markup.endswith("</g>")


def test_a_coil_comes_in_halves_that_wrap_a_rod() -> None:
    """The back half paints before the rod and the front half after it."""
    halves = _run(
        "const cam = Fig.camera();"
        "const [back, front] = Fig.coil(cam, { from: [0, 0, 20], to: [80, 0, 20], r: 8, turns: 5 });"
        "const rod = Fig.box(cam, { x: 0, y: -2, z: 18, w: 80, d: 4, h: 4 });"
        "[back.depth < rod.depth + 40, front.depth > back.depth, back.markup.includes('fig-coil-back'), front.markup.includes('fig-coil')]"
    )
    assert halves == [True, True, True, True]


def test_svg_paints_the_shadow_first_and_keeps_a_given_order() -> None:
    """Sorted, a shadow is at the back; unsorted, the order passed is the order painted."""
    order = _run(
        "const cam = Fig.camera();"
        "const near = Fig.box(cam, { x: 50, y: 50, w: 10, d: 10, h: 10, tone: 'near' });"
        "const far = Fig.box(cam, { x: -50, y: -50, w: 10, d: 10, h: 10, tone: 'far' });"
        "const sh = Fig.shadow(cam, { cx: 0, cy: 0, r: 20 });"
        "const sorted = Fig.svg([[near], far, sh]);"
        "const kept = Fig.svg([near, far], { sort: false });"
        "[sorted.indexOf('fig-sh') < sorted.indexOf('fig-far'), sorted.indexOf('fig-far') < sorted.indexOf('fig-near'),"
        " kept.indexOf('fig-near') < kept.indexOf('fig-far')]"
    )
    assert order == [True, True, True]


def test_its_colours_are_light_only() -> None:
    """Pages are light; the kit carries no dark scheme of its own."""
    css = _run("Fig.css")
    assert "prefers-color-scheme" not in css
    assert Path(KIT).read_text(encoding="utf-8").count("prefers-color-scheme") == 0
