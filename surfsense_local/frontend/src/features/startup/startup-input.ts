export type StartupDraft = { text: string; caret: number }

/**
 * What was typed into the startup frame's box, held for the composer that
 * replaces it, and whether an input method is mid-composition there. One per
 * app, made by AppBootstrap: the frame and the composer are siblings in its
 * tree, never the same component.
 */
export type StartupInput = {
  keep: (text: string, caret: number) => void
  peek: () => StartupDraft | null
  // After the composer has the text, so a composer mounted later starts empty.
  take: () => void
  setComposing: (active: boolean) => void
  // Handing over mid-composition would cut the input method's unconverted text.
  composingEnded: () => Promise<void>
}

export function createStartupInput(): StartupInput {
  let draft: StartupDraft | null = null
  let composing = false
  let waiting: (() => void)[] = []
  return {
    keep: (text, caret) => {
      draft = text ? { text, caret } : null
    },
    peek: () => draft,
    take: () => {
      draft = null
    },
    setComposing: (active) => {
      composing = active
      if (active) return
      const resolved = waiting
      waiting = []
      for (const resolve of resolved) resolve()
    },
    composingEnded: () =>
      composing
        ? new Promise<void>((resolve) => waiting.push(resolve))
        : Promise.resolve(),
  }
}
