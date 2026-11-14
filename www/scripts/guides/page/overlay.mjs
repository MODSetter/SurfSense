/**
 * Drawn into the page for the videos: a pointer that follows the mouse, since
 * headless Chromium draws none, a ring where it clicks, and a one-line caption.
 * Screenshots hide all of it (`window.__guide.hide()`), and the video cuts
 * those frames out.
 *
 * Runs in the page through `addInitScript`, so it must not close over anything.
 */
export function installOverlay() {
	const css = `
#guide-overlay { position: fixed; inset: 0; pointer-events: none; z-index: 2147483647; }
#guide-overlay.guide-hidden { display: none; }
#guide-pointer { position: absolute; left: 0; top: 0; width: 22px; height: 22px;
  transform: translate(-40px, -40px); transition: transform 520ms cubic-bezier(.3,.7,.2,1);
  filter: drop-shadow(0 1px 2px rgba(0,0,0,.35)); }
.guide-ring { position: absolute; width: 34px; height: 34px; margin: -17px 0 0 -17px;
  border-radius: 999px; border: 2px solid rgba(37,99,235,.9); background: rgba(37,99,235,.15);
  animation: guide-ring 520ms ease-out forwards; }
@keyframes guide-ring { from { transform: scale(.35); opacity: 1; } to { transform: scale(1.25); opacity: 0; } }
#guide-caption { position: absolute; left: 50%; bottom: 26px; transform: translateX(-50%);
  max-width: 78%; padding: 10px 18px; border-radius: 999px; background: rgba(23,23,23,.9);
  color: #fff; font: 500 15px/1.35 system-ui, sans-serif; text-align: center;
  opacity: 0; transition: opacity 240ms ease; }
#guide-caption.guide-shown { opacity: 1; }
html.guide-shot-quiet [data-sonner-toaster] { visibility: hidden !important; }`;

	let overlay;
	let pointer;
	let caption;
	const mount = () => {
		if (overlay?.isConnected) return;
		const style = document.createElement("style");
		style.textContent = css;
		document.head.append(style);
		overlay = document.createElement("div");
		overlay.id = "guide-overlay";
		overlay.innerHTML =
			'<svg id="guide-pointer" viewBox="0 0 22 22"><path d="M3 2 L3 18 L7.5 14 L10.5 20.5 L13.2 19.3 L10.3 13 L16.5 13 Z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg><div id="guide-caption"></div>';
		document.body.append(overlay);
		pointer = overlay.querySelector("#guide-pointer");
		caption = overlay.querySelector("#guide-caption");
	};
	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
	else mount();

	document.addEventListener(
		"mousemove",
		(event) => {
			mount();
			pointer.style.transform = `translate(${event.clientX - 3}px, ${event.clientY - 2}px)`;
		},
		true
	);
	document.addEventListener(
		"mousedown",
		(event) => {
			mount();
			const ring = document.createElement("div");
			ring.className = "guide-ring";
			ring.style.left = `${event.clientX}px`;
			ring.style.top = `${event.clientY}px`;
			overlay.append(ring);
			setTimeout(() => ring.remove(), 600);
		},
		true
	);

	window.__guide = {
		caption(text) {
			mount();
			if (text) caption.textContent = text;
			caption.classList.toggle("guide-shown", Boolean(text));
		},
		// Notices hide too, unless a screenshot is about one: they cover whatever sits under them.
		hide({ keepNotices = false } = {}) {
			mount();
			overlay.classList.add("guide-hidden");
			document.documentElement.classList.toggle("guide-shot-quiet", !keepNotices);
		},
		show() {
			overlay?.classList.remove("guide-hidden");
			document.documentElement.classList.remove("guide-shot-quiet");
		},
	};
}
