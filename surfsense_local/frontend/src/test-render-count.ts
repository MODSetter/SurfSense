import { createElement, memo, type ComponentType } from "react"

const MEMO = Symbol.for("react.memo")

type Memoized<P> = {
  $$typeof?: symbol
  type: ComponentType<P>
  compare?: ((previous: P, next: P) => boolean) | null
}

/**
 * For a `vi.mock` factory: the component, memoized as its module memoizes it,
 * calling `counted` on each render it really does.
 */
export function countRenders<P extends object>(
  component: ComponentType<P>,
  counted: (props: P) => void
): ComponentType<P> {
  const memoized = component as unknown as Memoized<P>
  const isMemo = memoized.$$typeof === MEMO
  const inner = isMemo ? memoized.type : component
  const Counted = (props: P) => {
    counted(props)
    return createElement(inner, props)
  }
  return isMemo
    ? (memo(
        Counted,
        memoized.compare ?? undefined
      ) as unknown as ComponentType<P>)
    : Counted
}
