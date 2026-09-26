// jsdom has no Web Animations API; Base UI calls it to wait for exit animations.
Element.prototype.getAnimations ??= () => []
// Nor pointer capture, which sonner takes when a toast is pressed, to swipe it away.
Element.prototype.setPointerCapture ??= () => {}
