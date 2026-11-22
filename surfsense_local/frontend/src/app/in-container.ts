/**
 * The Docker image's build (ADR 0075). Fixed at build time, so each build drops
 * the other's branches. Read it through a predicate named for the behaviour; what
 * only Electron can do is gated on its bridge instead, which a browser lacks too.
 */
export const IN_CONTAINER = import.meta.env.VITE_SURFSENSE_RUNTIME === "docker"
