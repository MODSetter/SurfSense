import {
  COMPOSER_CLASS,
  COMPOSER_CONTROLS_CLASS,
  COMPOSER_FOOTER_CLASS,
  composerBoxClass,
  composerInputClass,
  type ComposerPlacement,
} from "./composer-layout"

/**
 * The composer's empty box, the size ChatComposer draws it, for the startup
 * frame: its text and controls fade in when the real one takes its place.
 */
export function ComposerOutline({
  placement,
}: {
  placement: ComposerPlacement
}) {
  return (
    <div
      aria-hidden="true"
      className={COMPOSER_CLASS}
      data-composer-outline={placement}
    >
      <div className={composerBoxClass(placement)}>
        <div className={composerInputClass(placement)}>&nbsp;</div>
        {placement === "center" ? (
          <div className={COMPOSER_CONTROLS_CLASS} />
        ) : null}
      </div>
      {placement === "bottom" ? (
        <div className={COMPOSER_FOOTER_CLASS} />
      ) : null}
    </div>
  )
}
