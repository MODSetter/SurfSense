// Generates the air-gap diorama (isometric-mono style: stone, active step in blue) as `air-gap-diorama.svg`.
// Run: node components/homepage/home/home-air-gap/diorama/generate-air-gap-diorama.mjs
// Objects carry `data-group` (index / model / outputs) so scroll can light each step.

import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// ── Palettes: the scene in stone, the active step in the claim badges' blue ──
// Each step's objects are drawn once per ramp and stacked; the page crossfades
// the active step to its accent copy (`[data-dio="accent"]` in home.css).
// Hooks are data attributes, not classes: SVGR's SVGO prefixes class names.
const STONE = {
	OUT: "#2a2621",
	OW: "#fbfaf7",
	TONE1: "#efede7",
	TONE2: "#dedbd2",
	TONE3: "#bcb7ac",
	TONE4: "#8a8478",
	DARK: "#38342e",
};
const ACCENT = {
	OUT: "#1a2f55",
	OW: "#f7f9fd",
	TONE1: "#e3ecfa",
	TONE2: "#c4d6f4",
	TONE3: "#8fb0e8",
	TONE4: "#3f74c8",
	DARK: "#1d3561",
};
let OUT;
let OW;
let TONE1;
let TONE2;
let TONE3;
let TONE4;
let DARK;
let M;
function applyPalette(p) {
	({ OUT, OW, TONE1, TONE2, TONE3, TONE4, DARK } = p);
	M = {
		light: { top: OW, left: TONE2, right: TONE3 },
		pale: { top: OW, left: TONE1, right: TONE2 },
		mid: { top: OW, left: TONE3, right: TONE4 },
		deep: { top: DARK, left: TONE3, right: TONE4 },
		slab: { top: OW, left: TONE2, right: TONE3 },
		bevel: { top: TONE1, left: TONE3, right: TONE4 },
	};
}
applyPalette(STONE);

// ── Projection: true isometric, plan units scaled by K ─────────────────────
const K = 0.91;
const C30 = Math.cos(Math.PI / 6);
const P = (x, y, z = 0) => [240 + (x - y) * C30 * K, 204 + ((x + y) / 2 - z) * K];
const f = (n) => Math.round(n * 100) / 100;
const path = (pts, close = true) =>
	`M${pts.map(([x, y]) => `${f(x)} ${f(y)}`).join("L")}${close ? "Z" : ""}`;

const hex = (h) => [1, 3, 5].map((i) => Number.parseInt(h.slice(i, i + 2), 16));
const mix = (a, b, t) => {
	const [A, B] = [hex(a), hex(b)];
	return `#${A.map((v, i) =>
		Math.round(v + (B[i] - v) * t)
			.toString(16)
			.padStart(2, "0")
	).join("")}`;
};
// Side faces blend left (+y) and right (+x) colours by their normal.
const sideShade = (nx, ny, m) => {
	const t = Math.min(Math.max(((nx - ny) / (Math.abs(nx) + Math.abs(ny) || 1)) * 0.5 + 0.5, 0), 1);
	return mix(m.left, m.right, t);
};

// ── Output layers ──────────────────────────────────────────────────────────
const slab = [];
const floor = [];
const cast = [];
const highlights = [];
const objects = [];
let sink = objects;
const emit = (s) => sink.push(s);
const group = (name, draw) => {
	emit(`<g data-dio="obj" data-group="${name}">`);
	draw();
	emit('<g data-dio="accent">');
	applyPalette(ACCENT);
	draw();
	applyPalette(STONE);
	emit("</g></g>");
};

const fillFace = (pts, fill) =>
	emit(`<path d="${path(pts)}" fill="${fill}" stroke="${fill}" stroke-width="0.35"/>`);
const stroke = (d, color = OUT, w = 0.9, extra = "") =>
	emit(
		`<path d="${d}" fill="none" stroke="${color}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"${extra}/>`
	);
const both = (d, fill, color = OUT, w = 0.5) =>
	emit(
		`<path d="${d}" fill="${fill}" stroke="${color}" stroke-width="${w}" stroke-linejoin="round"/>`
	);

// ── Plan shapes ────────────────────────────────────────────────────────────
const circle = (cx, cy, r, n = 32) =>
	Array.from({ length: n }, (_, i) => {
		const a = (i / n) * Math.PI * 2;
		return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
	});
const rrect = (cx, cy, hw, hh, r, seg = 6) => {
	const pts = [];
	const corners = [
		[cx + hw - r, cy + hh - r, 0],
		[cx - hw + r, cy + hh - r, 90],
		[cx - hw + r, cy - hh + r, 180],
		[cx + hw - r, cy - hh + r, 270],
	];
	for (const [x, y, a0] of corners) {
		for (let i = 0; i <= seg; i++) {
			const a = ((a0 + (i / seg) * 90) * Math.PI) / 180;
			pts.push([x + Math.cos(a) * r, y + Math.sin(a) * r]);
		}
	}
	return pts;
};

// ── Solids ─────────────────────────────────────────────────────────────────
// A vertical prism over a plan polygon: visible sides back to front, then the top.
function prism(poly, z0, z1, m, outline = true) {
	const n = poly.length;
	const cx = poly.reduce((s, p) => s + p[0], 0) / n;
	const cy = poly.reduce((s, p) => s + p[1], 0) / n;
	const sides = [];
	for (let i = 0; i < n; i++) {
		const a = poly[i];
		const b = poly[(i + 1) % n];
		let nx = b[1] - a[1];
		let ny = -(b[0] - a[0]);
		const mx = (a[0] + b[0]) / 2;
		const my = (a[1] + b[1]) / 2;
		if (nx * (mx - cx) + ny * (my - cy) < 0) {
			nx = -nx;
			ny = -ny;
		}
		const len = Math.hypot(nx, ny) || 1;
		sides.push({ a, b, nx: nx / len, ny: ny / len, visible: nx + ny > 1e-6, depth: mx + my });
	}
	for (const s of [...sides].filter((s) => s.visible).sort((p, q) => p.depth - q.depth)) {
		fillFace(
			[P(s.a[0], s.a[1], z0), P(s.b[0], s.b[1], z0), P(s.b[0], s.b[1], z1), P(s.a[0], s.a[1], z1)],
			sideShade(s.nx, s.ny, m)
		);
	}
	const top = poly.map(([x, y]) => P(x, y, z1));
	fillFace(top, m.top);
	if (!outline) return;
	let d = path(top);
	for (let i = 0; i < n; i++) {
		const s = sides[i];
		const prev = sides[(i - 1 + n) % n];
		if (s.visible) d += path([P(s.a[0], s.a[1], z0), P(s.b[0], s.b[1], z0)], false);
		const turn = Math.acos(Math.min(1, s.nx * prev.nx + s.ny * prev.ny));
		if ((s.visible !== prev.visible || (s.visible && turn > 0.35)) && (s.visible || prev.visible)) {
			d += path([P(s.a[0], s.a[1], z0), P(s.a[0], s.a[1], z1)], false);
		}
	}
	stroke(d);
}
const box = (x0, x1, y0, y1, z0, z1, m, outline = true) =>
	prism(
		[
			[x0, y0],
			[x1, y0],
			[x1, y1],
			[x0, y1],
		],
		z0,
		z1,
		m,
		outline
	);

// Face mappers: draw in a face's own 2D coordinates.
const onLeft = (y) => (u, w) => P(u, y, w); // +y face: (x, z)
const onRight = (x) => (u, w) => P(x, u, w); // +x face: (y, z)
const onTop = (z) => (u, w) => P(u, w, z); // top: (x, y)
const quad = (F, u0, w0, u1, w1) => path([F(u0, w0), F(u1, w0), F(u1, w1), F(u0, w1)]);
const seg = (F, pts) =>
	path(
		pts.map(([u, w]) => F(u, w)),
		false
	);

// ── Floor decals ───────────────────────────────────────────────────────────
function hull(points) {
	const p = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
	const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
	const lower = [];
	for (const q of p) {
		while (lower.length >= 2 && cross(lower.at(-2), lower.at(-1), q) <= 0) lower.pop();
		lower.push(q);
	}
	const upper = [];
	for (const q of p.reverse()) {
		while (upper.length >= 2 && cross(upper.at(-2), upper.at(-1), q) <= 0) upper.pop();
		upper.push(q);
	}
	return lower.slice(0, -1).concat(upper.slice(0, -1));
}
// One light for the whole scene, never drawn: from the front left, high enough
// that a shadow is half as long as its caster is tall. Plan units per unit of height.
const LIGHT = (() => {
	const [dx, dy] = [1, -0.5];
	const n = Math.hypot(dx, dy);
	return [(dx / n) * 0.5, (dy / n) * 0.5];
})();
const onFloor = ([x, y, z]) => [x + z * LIGHT[0], y + z * LIGHT[1]];
const solid = (foot, z0, z1) => [
	...foot.map(([x, y]) => [x, y, z0]),
	...foot.map(([x, y]) => [x, y, z1]),
];
// Each convex part's corners pushed along the light by their height. Parts are
// drawn opaque in one group faded once, so overlapping shadows never darken.
const castShadow = (...parts) => {
	for (const corners of parts)
		cast.push(`<path d="${path(hull(corners.map(onFloor)).map(([x, y]) => P(x, y, 0)))}"/>`);
};
// Where an object meets the slab: a tight band under its footprint, undirected.
const contact = (foot, grow = 2.5, alpha = 0.5) => {
	const cx = foot.reduce((s, p) => s + p[0], 0) / foot.length;
	const cy = foot.reduce((s, p) => s + p[1], 0) / foot.length;
	const out = foot.map(([x, y]) => {
		const d = Math.hypot(x - cx, y - cy) || 1;
		return [x + ((x - cx) / d) * grow, y + ((y - cy) / d) * grow];
	});
	floor.push(
		`<path d="${path(out.map(([x, y]) => P(x, y, 0)))}" fill="${TONE4}" fill-opacity="${alpha}"/>`
	);
};
const ellipse = (cx, cy, rx, ry, z = 0) =>
	Array.from({ length: 36 }, (_, i) => {
		const a = (i / 36) * Math.PI * 2;
		return P(cx + Math.cos(a) * rx, cy + Math.sin(a) * ry, z);
	});
const highlight = (name, spots) =>
	highlights.push(
		`<g data-dio="glow" data-glow="${name}">${spots
			.map(
				([cx, cy, rx, ry]) => `<path d="${path(ellipse(cx, cy, rx, ry))}" fill="${ACCENT.TONE3}"/>`
			)
			.join("")}</g>`
	);

// ── Cables: Catmull-Rom through plan points ────────────────────────────────
function curve(pts3) {
	const p = pts3.map(([x, y, z]) => P(x, y, z));
	let d = `M${f(p[0][0])} ${f(p[0][1])}`;
	for (let i = 0; i < p.length - 1; i++) {
		const p0 = p[i - 1] ?? p[i];
		const p1 = p[i];
		const p2 = p[i + 1];
		const p3 = p[i + 2] ?? p2;
		const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
		const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
		d += `C${f(c1[0])} ${f(c1[1])} ${f(c2[0])} ${f(c2[1])} ${f(p2[0])} ${f(p2[1])}`;
	}
	return d;
}
const cable = (pts3) => {
	const d = curve(pts3);
	stroke(d, OUT, 3);
	stroke(d, TONE3, 1.55);
	stroke(d, TONE1, 0.5, ' transform="translate(-0.35 -0.45)"');
};
const cableShadow = (pts) =>
	floor.push(
		`<path d="${curve(pts.map((p) => [...onFloor(p), 0]))}" fill="none" stroke="${TONE4}" stroke-opacity="0.3" stroke-width="3"/>`
	);

// ── Slab ───────────────────────────────────────────────────────────────────
const SLAB = rrect(0, 0, 122, 122, 26, 8);
function platform() {
	sink = slab;
	prism(SLAB, -12, -7, M.bevel);
	prism(SLAB, -7, 0, M.slab);
	const rim = rrect(0, 0, 115.5, 115.5, 20, 8).map(([x, y]) => P(x, y, 0));
	stroke(path(rim), TONE3, 0.6, ' stroke-opacity="0.75"');
	sink = objects;
}

// ── Objects ────────────────────────────────────────────────────────────────
function laptop() {
	// Base and keyboard.
	box(-30, 30, -16, 24, 0, 4, M.light);
	const T = onTop(4);
	both(quad(T, -26, -12, 26, 8), DARK, OUT, 0.5);
	let keys = "";
	for (let y = -10.5; y <= 6; y += 3.4) {
		for (let x = -24; x <= 23; x += 3.6) keys += quad(T, x, y, x + 2.6, y + 2.4);
	}
	emit(`<path d="${keys}" fill="${TONE4}" stroke="${DARK}" stroke-width="0.35"/>`);
	both(quad(T, -9, 11, 9, 21), TONE1, OUT, 0.5);
	// Screen standing at the back edge, facing +y.
	box(-30, 30, -19, -16, 4, 44, M.mid);
	const S = onLeft(-16);
	both(quad(S, -27, 7, 27, 41), DARK, OUT, 0.55);
	// A chat, not code: the product is asking questions of your own sources.
	const bubble = (u0, w0, u1, w1, r, fill) =>
		both(
			path(
				rrect((u0 + u1) / 2, (w0 + w1) / 2, (u1 - u0) / 2, (w1 - w0) / 2, r).map(([u, w]) =>
					S(u, w)
				)
			),
			fill,
			fill,
			0.3
		);
	const line = (u0, u1, w, color) =>
		stroke(
			seg(S, [
				[u0, w],
				[u1, w],
			]),
			color,
			1
		);
	// Question, right-aligned.
	bubble(2, 33, 24, 39, 2.2, TONE2);
	line(5, 20, 36, DARK);
	// Answer, left-aligned, citing a source.
	bubble(-24, 16.5, 12, 30.5, 2.2, TONE4);
	line(-21, 7, 27.5, TONE1);
	line(-21, 3, 24, TONE1);
	line(-21, -8, 20, TONE1);
	bubble(-6, 18.6, 3, 21.4, 1.4, ACCENT.TONE4);
	// Input bar with its send button.
	both(path(rrect(0, 11, 24, 2.6, 2.4).map(([u, w]) => S(u, w))), "none", TONE3, 0.5);
	bubble(19, 9.2, 22.6, 12.8, 1.6, TONE1);
	emit(`<path d="${quad(S, -27, 7, 27, 41)}" fill="${TONE3}" fill-opacity="0.18"/>`);
}

// 96 sides: at 32 the facets and shading bands show at hero size.
const DB_SIDES = 96;
// Points along a circle at height z, so a mark follows the cylinder's curve.
const arc = (cx, cy, r, a0, a1, z, n = 8) =>
	Array.from({ length: n + 1 }, (_, i) => {
		const a = a0 + ((a1 - a0) * i) / n;
		return [cx + Math.cos(a) * r, cy + Math.sin(a) * r, z];
	});
function database() {
	const [cx, cy, r] = [-78, -24, 17];
	const discs = [
		[0, 10],
		[11.5, 21.5],
		[23, 33],
	];
	for (const [z0, z1] of discs) {
		if (z0 > 0) prism(circle(cx, cy, r - 1.5, DB_SIDES), z0 - 1.5, z0, M.deep);
		prism(circle(cx, cy, r, DB_SIDES), z0, z1, M.light);
		// Drive bay on the front of each disc, mid-height: status light, then a
		// slot grooved round the cylinder (dark cut over a lit lower lip).
		const zm = (z0 + z1) / 2;
		const front = Math.PI / 4; // faces the viewer; larger angles sit further left
		const [lx, ly] = P(cx + Math.cos(front + 0.42) * r, cy + Math.sin(front + 0.42) * r, zm);
		emit(
			`<circle cx="${f(lx)}" cy="${f(ly)}" r="0.8" fill="${TONE1}" stroke="${OUT}" stroke-width="0.35"/>`
		);
		stroke(curve(arc(cx, cy, r, front + 0.27, front - 0.36, zm - 0.55)), OW, 0.4);
		stroke(curve(arc(cx, cy, r, front + 0.27, front - 0.36, zm)), TONE4, 0.55);
	}
	// Top: concentric rings name it a store.
	stroke(path(circle(cx, cy, 10, DB_SIDES).map(([x, y]) => P(x, y, 33))), TONE3, 0.55);
	stroke(path(circle(cx, cy, 4.5, DB_SIDES).map(([x, y]) => P(x, y, 33))), TONE3, 0.55);
}

// A router with its link dead: unlit LEDs, a Wi-Fi-off glyph, an empty port.
function router() {
	const [cx, cy, hw, hh, h] = [-72, 70, 16, 10, 12];
	const [x0, x1, y0, y1] = [cx - hw, cx + hw, cy - hh, cy + hh];
	// Antennas at the back, drawn first so the box covers their feet.
	for (const ax of [x0 + 5, x1 - 5]) {
		box(ax - 0.9, ax + 0.9, y0 + 2, y0 + 3.8, h, h + 20, M.mid);
		prism(circle(ax, y0 + 2.9, 1.5, 12), h + 20, h + 22, M.light);
	}
	box(x0, x1, y0, y1, 0, h, M.light);
	// Vents on top.
	const T = onTop(h);
	let vents = "";
	for (let x = x0 + 9; x <= x1 - 4; x += 2.2)
		vents += seg(T, [
			[x, y0 + 7],
			[x, y1 - 3],
		]);
	stroke(vents, TONE4, 0.45, ' stroke-opacity="0.7"');
	// Front (+y): a dark panel with three unlit LEDs and the Wi-Fi-off glyph.
	const F = onLeft(y1);
	both(quad(F, x0 + 3, 2.5, x1 - 3, h - 2.5), DARK, OUT, 0.5);
	for (const u of [x0 + 6, x0 + 9.5, x0 + 13]) {
		const [lx, ly] = F(u, h / 2);
		emit(
			`<circle cx="${f(lx)}" cy="${f(ly)}" r="0.85" fill="${TONE4}" stroke="${OUT}" stroke-width="0.35"/>`
		);
	}
	const [gu, gw] = [x1 - 9, 3.6];
	for (const r of [2, 3.8, 5.6]) {
		const arc = Array.from({ length: 9 }, (_, i) => {
			const t = ((45 + i * 11.25) * Math.PI) / 180;
			return [gu + Math.cos(t) * r, gw + Math.sin(t) * r];
		});
		stroke(seg(F, arc), TONE2, 0.75);
	}
	const [dx, dy] = F(gu, gw + 0.6);
	emit(`<circle cx="${f(dx)}" cy="${f(dy)}" r="0.6" fill="${TONE2}"/>`);
	stroke(
		seg(F, [
			[gu - 4.5, gw + 0.3],
			[gu + 4.5, gw + 6.8],
		]),
		TONE1,
		1
	);
	// Side facing the laptop (+x): an empty ethernet port.
	const R = onRight(x1);
	both(quad(R, cy - 3.5, 3, cy + 3.5, 8.5), DARK, OUT, 0.5);
	stroke(
		seg(R, [
			[cy - 2, 7],
			[cy + 2, 7],
		]),
		TONE4,
		0.45
	);
}

// The unplugged lead's plug, lying on the slab beside the empty port.
function loosePlug() {
	const [px, py] = [-48, 58];
	box(px - 2.5, px + 2.5, py - 4, py + 4, 0, 3.2, M.pale);
	both(quad(onLeft(py + 4), px - 1.6, 0.8, px + 1.6, 2.6), TONE3, OUT, 0.35);
}

function rack() {
	const [x0, x1, y0, y1, h] = [20, 58, -108, -84, 78];
	box(x0, x1, y0, y1, 0, h, M.mid);
	const F = onLeft(y1);
	both(quad(F, x0 + 3, 4, x1 - 3, h - 4), DARK, OUT, 0.55);
	for (let z = 7; z < h - 6; z += 6.4) {
		both(quad(F, x0 + 5, z, x1 - 5, z + 4.6), TONE4, DARK, 0.35);
		const [lx, ly] = F(x1 - 8, z + 2.3);
		emit(`<circle cx="${f(lx)}" cy="${f(ly)}" r="0.75" fill="${TONE1}"/>`);
		stroke(
			seg(F, [
				[x0 + 8, z + 2.3],
				[x0 + 18, z + 2.3],
			]),
			TONE3,
			0.5
		);
	}
	// Vents on the +x side.
	const R = onRight(x1);
	let vents = "";
	for (let z = 10; z < h - 8; z += 2.2)
		vents += seg(R, [
			[y0 + 5, z],
			[y1 - 5, z],
		]);
	stroke(vents, DARK, 0.45, ' stroke-opacity="0.6"');
	// Chip glyph on top: the model lives here.
	const T = onTop(h);
	both(quad(T, 31, -102, 47, -90), DARK, OUT, 0.5);
	let pins = "";
	for (let x = 33.5; x <= 45; x += 3)
		pins +=
			seg(T, [
				[x, -104.5],
				[x, -102],
			]) +
			seg(T, [
				[x, -90],
				[x, -87.5],
			]);
	stroke(pins, OUT, 0.45);
}

function keyCard() {
	const [cx, cy] = [80, -30];
	prism(rrect(cx, cy, 17, 12, 3), 0, 3, M.deep);
	const T = onTop(3);
	const ring = circle(cx - 7, cy, 4.2, 20).map(([x, y]) => T(x, y));
	stroke(path(ring), TONE1, 1.1);
	stroke(
		seg(T, [
			[cx - 2.8, cy],
			[cx + 11, cy],
		]),
		TONE1,
		1.1
	);
	stroke(
		seg(T, [
			[cx + 7, cy],
			[cx + 7, cy + 4],
		]),
		TONE1,
		1.1
	);
	stroke(
		seg(T, [
			[cx + 10, cy],
			[cx + 10, cy + 3],
		]),
		TONE1,
		1.1
	);
}

function report() {
	const [x0, x1, y0, y1, h] = [96, 102, 14, 46, 42];
	box(x0, x1, y0, y1, 0, h, M.light);
	const R = onRight(x1);
	both(quad(R, y0 + 3, 4, y1 - 3, h - 4), OW, OUT, 0.5);
	let lines = "";
	for (let z = h - 12; z > 10; z -= 3.2)
		lines += seg(R, [
			[y0 + 6, z],
			[y1 - (z % 2 ? 10 : 6), z],
		]);
	stroke(lines, TONE3, 0.6);
	stroke(
		seg(R, [
			[y0 + 6, h - 8],
			[y0 + 18, h - 8],
		]),
		TONE4,
		1.2
	);
	// Tick: the report is done.
	stroke(
		seg(R, [
			[y1 - 12, 9],
			[y1 - 9.5, 6.5],
			[y1 - 5, 11],
		]),
		TONE4,
		1
	);
}

function deckStack() {
	const [cx, cy] = [60, 80];
	const slabs = [
		[0, 3, 0],
		[4, 7, 2.5],
		[8, 11, -2],
	];
	for (const [z0, z1, dx] of slabs) prism(rrect(cx + dx, cy - dx, 21, 15, 2.5), z0, z1, M.light);
	// Top slide: a frame with a small bar chart.
	const T = onTop(11);
	both(quad(T, cx - 17, cy + 1, cx + 15, cy - 13), OW, OUT, 0.5);
	stroke(
		seg(T, [
			[cx - 14, cy - 10],
			[cx - 2, cy - 10],
		]),
		TONE4,
		1.2
	);
	const bars = [
		[cx + 2, 6],
		[cx + 6, 10],
		[cx + 10, 4],
	];
	for (const [x, len] of bars) both(quad(T, x, cy - 2, x + 2.6, cy - 2 - len), TONE3, OUT, 0.4);
	stroke(
		seg(T, [
			[cx - 14, cy - 6],
			[cx - 4, cy - 6],
		]),
		TONE2,
		0.9
	);
	stroke(
		seg(T, [
			[cx - 14, cy - 3],
			[cx - 6, cy - 3],
		]),
		TONE2,
		0.9
	);
}

// ── Scene ──────────────────────────────────────────────────────────────────
// Each cable starts under the laptop base (x > -30), so the base hides its tip.
const DB_CABLE = [
	[-25, -1.79, 1.1],
	[-30, -3.57, 1.1],
	[-34, -5, 1.1],
	[-48, -10, 1.1],
	[-56, -19, 1.1],
	[-61.2, -21.5, 2.5],
];
const LOOSE_CABLE = [
	[-25, 11.5, 2.5],
	[-30, 14, 2.5],
	[-34, 16, 1.1],
	[-42, 28, 1.1],
	[-46, 44, 1.1],
	[-48, 54, 1.6],
];

platform();

// Footprints and heights match each object's own geometry below.
const rect = (x0, x1, y0, y1) => [
	[x0, y0],
	[x1, y0],
	[x1, y1],
	[x0, y1],
];
const DB_FOOT = circle(-78, -24, 17, DB_SIDES);
const RACK_FOOT = rect(20, 58, -108, -84);
const LAPTOP_FOOT = rect(-30, 30, -19, 24);
const ROUTER_FOOT = rect(-88, -56, 60, 80);
const PLUG_FOOT = rect(-50.5, -45.5, 54, 62);
const KEY_FOOT = rrect(80, -30, 17, 12, 3, 2);
const REPORT_FOOT = rect(96, 102, 14, 46);
const DECK = [
	[0, 3, 0],
	[4, 7, 2.5],
	[8, 11, -2],
].map(([z0, z1, dx]) => [rrect(60 + dx, 80 - dx, 21, 15, 2.5, 2), z0, z1]);

castShadow(solid(DB_FOOT, 0, 33));
castShadow(solid(RACK_FOOT, 0, 78));
castShadow(solid(rect(-30, 30, -16, 24), 0, 4), solid(rect(-30, 30, -19, -16), 0, 44));
castShadow(
	solid(ROUTER_FOOT, 0, 12),
	solid(rect(-84, -82, 61.5, 64.3), 0, 34),
	solid(rect(-62, -60, 61.5, 64.3), 0, 34)
);
castShadow(solid(PLUG_FOOT, 0, 3.2));
castShadow(solid(KEY_FOOT, 0, 3));
castShadow(solid(REPORT_FOOT, 0, 42));
castShadow(...DECK.map(([foot, , z1]) => solid(foot, 0, z1)));

for (const foot of [DB_FOOT, RACK_FOOT, LAPTOP_FOOT, ROUTER_FOOT, REPORT_FOOT, DECK[0][0]])
	contact(foot);
contact(PLUG_FOOT, 1.5);
contact(KEY_FOOT, 1.5);
cableShadow(DB_CABLE);
cableShadow(LOOSE_CABLE);

highlight("index", [
	[-78, -24, 34, 30],
	[-72, 70, 28, 22],
]);
highlight("model", [
	[39, -78, 34, 26],
	[80, -30, 26, 20],
]);
highlight("outputs", [
	[60, 80, 32, 26],
	[99, 30, 18, 26],
]);

// Back to front by footprint depth (x + y).
group("index", () => {
	database();
	cable(DB_CABLE);
});
group("model", rack);
group("index", router);
group("index", () => {
	cable(LOOSE_CABLE);
	loosePlug();
});
laptop();
group("model", keyCard);
group("outputs", report);
group("outputs", deckStack);

// ── Assemble ───────────────────────────────────────────────────────────────
const slabTop = path(SLAB.map(([x, y]) => P(x, y, 0)));
const svg = [
	`<svg xmlns="http://www.w3.org/2000/svg" viewBox="40 30 400 316">`,
	"<defs>",
	`<clipPath id="dio-slab"><path d="${slabTop}"/></clipPath>`,
	`<filter id="dio-soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="1.6"/></filter>`,
	`<filter id="dio-under" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="4"/></filter>`,
	`<filter id="dio-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7"/></filter>`,
	"</defs>",
	`<path d="${path(SLAB.map(([x, y]) => P(...onFloor([x, y, 12]), -12)))}" fill="${TONE3}" fill-opacity="0.2" filter="url(#dio-under)"/>`,
	slab.join(""),
	`<g clip-path="url(#dio-slab)"><g filter="url(#dio-soft)"><g fill="${TONE4}" opacity="0.34">${cast.join("")}</g>${floor.join("")}</g><g filter="url(#dio-glow)">${highlights.join("")}</g></g>`,
	objects.join(""),
	"</svg>",
].join("");

const here = dirname(fileURLToPath(import.meta.url));
writeFileSync(join(here, "air-gap-diorama.svg"), `${svg}\n`);
if (process.argv[2]) writeFileSync(process.argv[2], svg);
console.log(`diorama: ${svg.length} bytes`);
