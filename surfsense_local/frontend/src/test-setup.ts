// jsdom has no Web Animations API; Base UI calls it to wait for exit animations.
Element.prototype.getAnimations ??= () => []
