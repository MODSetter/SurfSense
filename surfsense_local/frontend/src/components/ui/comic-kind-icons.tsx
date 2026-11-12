import { type SVGProps, useId } from "react"

import {
  Bubble,
  Ground,
  INK,
  Panel,
  PictureArt,
  Sheet,
  burst,
} from "./picture-art"

// Each kind of comic Studio draws, as a picture for its card.
// SVG's own from and to animate; here they name a picture's backdrop colours.
type ArtProps = Omit<SVGProps<SVGSVGElement>, "from" | "to">

/** A page of colour panels, a speech bubble and a POW burst. */
export function WesternComicIcon(props: ArtProps) {
  return (
    <PictureArt from="#dbeafe" to="#e0e7ff" {...props}>
      <Ground />
      <Sheet x="34" y="8" width="52" height="62" />
      <Panel x="38" y="12" width="44" height="20" fill="#93c5fd" />
      <path
        d="M38 32 V26 H43 V22 H48 V27 H52 V20 H57 V25 H62 V32 Z"
        fill="#3b82f6"
      />
      <Bubble cx={70} cy={19} />
      <Panel x="38" y="35" width="20" height="31" fill="#fca5a5" />
      <circle
        cx="48"
        cy="47"
        r="5"
        fill="#fde68a"
        stroke={INK}
        strokeWidth="0.7"
      />
      <path d="M43 66 C43 58 53 58 53 66 Z" fill="#ef4444" />
      <Panel x="61" y="35" width="21" height="31" fill="#fde68a" />
      <path d="M64 63 L71 41 L78 63 Z" fill="#fb923c" opacity="0.8" />
      <polygon
        points={burst(92, 27, 13, 7.5)}
        fill="#facc15"
        stroke={INK}
        strokeWidth="0.8"
        strokeLinejoin="round"
      />
      <polygon points={burst(92, 27, 7, 4)} fill="#ef4444" />
    </PictureArt>
  )
}

/** A hardcover: a moonlit cover on a thick block of pages. */
export function GraphicNovelIcon(props: ArtProps) {
  const cover = `${useId()}-cover`
  return (
    <PictureArt from="#ede9fe" to="#fae8ff" {...props}>
      <defs>
        <linearGradient id={cover} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#7c3aed" />
          <stop offset="1" stopColor="#4c1d95" />
        </linearGradient>
      </defs>
      <Ground />
      <rect
        x="40"
        y="10"
        width="44"
        height="60"
        rx="2"
        fill="#f5f5f4"
        stroke={INK}
        strokeOpacity="0.45"
        strokeWidth="1"
      />
      <path d="M81 12 V68 M83 13 V67" stroke="#d6d3d1" strokeWidth="0.6" />
      <rect
        x="36"
        y="8"
        width="44"
        height="60"
        rx="2.5"
        fill={`url(#${cover})`}
        stroke={INK}
        strokeOpacity="0.6"
        strokeWidth="1"
      />
      <rect x="36" y="8" width="5" height="60" rx="1.5" fill="#3b0764" />
      <circle cx="66" cy="22" r="6" fill="#fde68a" />
      <circle cx="68.5" cy="20.5" r="5" fill="#6d28d9" />
      <path d="M41 52 L52 40 L60 47 L69 36 L80 46 V68 H41 Z" fill="#2e1065" />
      <rect
        x="46"
        y="56"
        width="26"
        height="3"
        rx="1.5"
        fill="#ffffff"
        opacity="0.9"
      />
      <rect
        x="50"
        y="61"
        width="18"
        height="2"
        rx="1"
        fill="#ffffff"
        opacity="0.55"
      />
      <circle cx="49" cy="17" r="0.9" fill="#ffffff" />
      <circle cx="56" cy="26" r="0.7" fill="#ffffff" />
      <circle cx="74" cy="32" r="0.7" fill="#ffffff" />
    </PictureArt>
  )
}

/** An album page in clean lines and flat colour, nine small panels. */
export function BandeDessineeIcon(props: ArtProps) {
  const fills = [
    "#93c5fd",
    "#fde68a",
    "#fca5a5",
    "#86efac",
    "#ffffff",
    "#93c5fd",
    "#fdba74",
    "#c4b5fd",
    "#fde68a",
  ]
  return (
    <PictureArt from="#ffedd5" to="#fef3c7" {...props}>
      <Ground />
      <Sheet x="31" y="7" width="58" height="64" />
      {fills.map((fill, i) => (
        <Panel
          key={fill + i}
          x={35 + (i % 3) * 17.3}
          y={11 + Math.floor(i / 3) * 19.6}
          width="15.3"
          height="17.6"
          fill={fill}
        />
      ))}
      <Bubble cx={60.5} cy={35.5} rx={5} ry={3} />
      <circle cx="43" cy="21" r="3" fill="#fbbf24" />
      <path
        d="M35 28.6 L41 23 L45 26 L50.3 21.5 V28.6 Z"
        fill="#2563eb"
        opacity="0.7"
      />
      <path d="M78 66 l2.5 -5 l2.5 5 Z" fill="#ef4444" />
    </PictureArt>
  )
}

/** A black-and-white page: screentone, speed lines and a wide eye, read right to left. */
export function MangaIcon(props: ArtProps) {
  const tone = `${useId()}-tone`
  return (
    <PictureArt from="#fce7f3" to="#f5f3ff" {...props}>
      <defs>
        <pattern
          id={tone}
          width="2.6"
          height="2.6"
          patternUnits="userSpaceOnUse"
        >
          <circle cx="1.3" cy="1.3" r="0.55" fill={INK} opacity="0.55" />
        </pattern>
      </defs>
      <Ground />
      <Sheet x="36" y="8" width="48" height="62" />
      <Panel x="40" y="12" width="40" height="24" fill="#ffffff" />
      <path
        d="M41 13 L60 24 M41 22 L60 24 M41 34 L60 24 M79 13 L60 24 M79 30 L60 24 M70 35 L60 24 M50 13 L60 24"
        stroke={INK}
        strokeOpacity="0.35"
        strokeWidth="0.6"
      />
      <path
        d="M49 24 C53 18 67 18 71 24 C67 30 53 30 49 24 Z"
        fill="#ffffff"
        stroke={INK}
        strokeWidth="1"
      />
      <circle cx="60" cy="24" r="4.2" fill={INK} />
      <circle cx="61.4" cy="22.6" r="1.3" fill="#ffffff" />
      <Panel x="61" y="39" width="19" height="27" fill={`url(#${tone})`} />
      <Panel x="40" y="39" width="18" height="27" fill="#ffffff" />
      <ellipse
        cx="49"
        cy="50"
        rx="5.5"
        ry="7.5"
        fill="#ffffff"
        stroke={INK}
        strokeWidth="0.7"
      />
      <path
        d="M47 46 V54 M50.5 45 V55"
        stroke={INK}
        strokeWidth="0.9"
        strokeLinecap="round"
      />
      <path
        d="M100 15 H90 M93 12 L90 15 L93 18"
        stroke="#ec4899"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </PictureArt>
  )
}

/** A painterly page: a sunset over mountains, and a red lantern. */
export function ManhuaIcon(props: ArtProps) {
  const sunset = `${useId()}-sunset`
  return (
    <PictureArt from="#fee2e2" to="#ffedd5" {...props}>
      <defs>
        <linearGradient id={sunset} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fb923c" />
          <stop offset="1" stopColor="#f43f5e" />
        </linearGradient>
      </defs>
      <Ground />
      <Sheet x="36" y="8" width="48" height="62" />
      <Panel x="40" y="12" width="40" height="28" fill={`url(#${sunset})`} />
      <circle cx="66" cy="22" r="5" fill="#fde68a" opacity="0.9" />
      <path d="M40.4 40 L48 27 L55 34 L63 24 L79.6 39.6 V40 Z" fill="#9f1239" />
      <path d="M40.4 40 L46 34 L53 38 L58 33 L68 40 Z" fill="#4c0519" />
      <Panel x="40" y="43" width="40" height="23" fill="#fef3c7" />
      <path d="M51 43 V47" stroke="#b45309" strokeWidth="0.8" />
      <rect x="47.5" y="47" width="7" height="2" rx="0.6" fill="#f59e0b" />
      <ellipse cx="51" cy="54" rx="6" ry="5.5" fill="#dc2626" />
      <path
        d="M48 50 Q51 54 48 58 M54 50 Q51 54 54 58"
        stroke="#991b1b"
        strokeWidth="0.6"
      />
      <rect x="47.5" y="58.5" width="7" height="2" rx="0.6" fill="#f59e0b" />
      <path d="M51 60.5 V64" stroke="#f59e0b" strokeWidth="1" />
      <path
        d="M62 49 H75 M62 53 H72 M62 57 H74"
        stroke="#d6b88a"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </PictureArt>
  )
}

/** A phone of tall panels stacked to scroll down. */
export function WebtoonIcon(props: ArtProps) {
  const screen = `${useId()}-screen`
  return (
    <PictureArt from="#d1fae5" to="#cffafe" {...props}>
      <defs>
        <clipPath id={screen}>
          <rect x="46.5" y="10" width="27" height="58" rx="2" />
        </clipPath>
      </defs>
      <Ground rx={22} />
      <rect x="44" y="6" width="32" height="66" rx="5" fill={INK} />
      <rect x="46.5" y="10" width="27" height="58" rx="2" fill="#ffffff" />
      <g clipPath={`url(#${screen})`}>
        <Panel x="48.5" y="12" width="23" height="17" fill="#a7f3d0" />
        <circle cx="64" cy="18" r="3.5" fill="#fbbf24" />
        <path d="M48.5 29 L55 22 L61 29 Z" fill="#10b981" />
        <Panel x="48.5" y="32" width="23" height="17" fill="#bfdbfe" />
        <Bubble cx={57} cy={38} rx={5} ry={3} />
        <Panel x="48.5" y="52" width="23" height="17" fill="#fbcfe8" />
        <circle cx="60" cy="61" r="4" fill="#f472b6" />
      </g>
      <rect x="55" y="7.5" width="10" height="1.5" rx="0.75" fill="#475569" />
      <path
        d="M88 22 V54 M84 50 L88 55 L92 50"
        stroke="#10b981"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M88 22 V54"
        stroke="#10b981"
        strokeWidth="1.8"
        strokeDasharray="3 3"
        strokeLinecap="round"
      />
    </PictureArt>
  )
}

/** Three panels in a row, the punchline last. */
export function ComicStripIcon(props: ArtProps) {
  return (
    <PictureArt from="#fef9c3" to="#fde68a" {...props}>
      <Ground rx={46} />
      <Sheet x="12" y="22" width="96" height="38" />
      <Panel x="15.5" y="25.5" width="28" height="31" fill="#bae6fd" />
      <Panel x="46" y="25.5" width="28" height="31" fill="#c7d2fe" />
      <Panel x="76.5" y="25.5" width="28" height="31" fill="#fecaca" />
      <Bubble cx={26} cy={32} rx={6} ry={3.2} />
      <circle
        cx="31"
        cy="48"
        r="4.5"
        fill="#fde68a"
        stroke={INK}
        strokeWidth="0.7"
      />
      <Bubble cx={57} cy={32} rx={6} ry={3.2} />
      <circle
        cx="62"
        cy="48"
        r="4.5"
        fill="#fde68a"
        stroke={INK}
        strokeWidth="0.7"
      />
      <polygon
        points={burst(90, 36, 7, 3.5, 8)}
        fill="#facc15"
        stroke={INK}
        strokeWidth="0.7"
        strokeLinejoin="round"
      />
      <circle
        cx="92"
        cy="49"
        r="4.5"
        fill="#fde68a"
        stroke={INK}
        strokeWidth="0.7"
      />
      <path
        d="M90 50 Q92 52 94 50"
        stroke={INK}
        strokeWidth="0.7"
        strokeLinecap="round"
      />
    </PictureArt>
  )
}

/** Four equal panels stacked top to bottom, its title down the side. */
export function YonkomaIcon(props: ArtProps) {
  const fills = ["#fde68a", "#bbf7d0", "#bfdbfe", "#fecaca"]
  return (
    <PictureArt from="#ede9fe" to="#e0e7ff" {...props}>
      <Ground rx={20} />
      <Sheet x="45" y="5" width="30" height="67" />
      {fills.map((fill, i) => (
        <Panel
          key={fill}
          x="48.5"
          y={8.5 + i * 15.6}
          width="23"
          height="13.6"
          fill={fill}
        />
      ))}
      <circle cx="56" cy="15" r="2.6" fill="#fb923c" />
      <circle cx="62" cy="31" r="2.6" fill="#22c55e" />
      <circle cx="58" cy="46" r="2.6" fill="#3b82f6" />
      <polygon points={burst(60, 62, 4, 2, 6)} fill="#ef4444" />
      <rect
        x="78"
        y="9"
        width="3.5"
        height="26"
        rx="1.75"
        fill={INK}
        opacity="0.75"
      />
      <rect x="78" y="38" width="3.5" height="10" rx="1.75" fill="#a78bfa" />
    </PictureArt>
  )
}

/** An open book: a sunny picture on one page, its words on the other. */
export function PictureBookIcon(props: ArtProps) {
  return (
    <PictureArt from="#dcfce7" to="#ecfccb" {...props}>
      <Ground rx={42} />
      <path
        d="M60 66 C50 61 33 61 18 64 V16 C33 13 50 13 60 18 C70 13 87 13 102 16 V64 C87 61 70 61 60 66 Z"
        fill="#f97316"
      />
      <path
        d="M60 62 C50 57 34 57 21 60 V14 C34 11 50 11 60 16 Z"
        fill="#ffffff"
        stroke={INK}
        strokeOpacity="0.45"
        strokeWidth="1"
        strokeLinejoin="round"
      />
      <path
        d="M60 62 C70 57 86 57 99 60 V14 C86 11 70 11 60 16 Z"
        fill="#ffffff"
        stroke={INK}
        strokeOpacity="0.45"
        strokeWidth="1"
        strokeLinejoin="round"
      />
      <path
        d="M24 50 C33 44 46 46 57 51 V57 C46 54 34 54 24 56 Z"
        fill="#86efac"
      />
      <circle cx="47" cy="24" r="4.5" fill="#fbbf24" />
      <rect x="31" y="38" width="2.6" height="12" rx="1" fill="#a16207" />
      <circle cx="32.3" cy="35" r="6" fill="#22c55e" />
      <circle cx="29" cy="33" r="1" fill="#f472b6" />
      <path
        d="M66 22 H92 M66 28 H90 M66 34 H93 M66 40 H86 M66 46 H91"
        stroke="#cbd5e1"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M85 53 C85 51 88 51 88 53 C88 51 91 51 91 53 C91 55.5 88 57 88 57 C88 57 85 55.5 85 53 Z"
        fill="#f472b6"
      />
    </PictureArt>
  )
}

/** A sheet of rough frames, each a shot, with arrows and a camera. */
export function StoryboardIcon(props: ArtProps) {
  const frames: [number, number][] = [
    [29, 13],
    [62, 13],
    [29, 41],
    [62, 41],
  ]
  return (
    <PictureArt from="#e2e8f0" to="#dbeafe" {...props}>
      <Ground rx={38} />
      <Sheet x="24" y="8" width="72" height="62" />
      {frames.map(([x, y]) => (
        <g key={`${x}-${y}`}>
          <rect
            x={x}
            y={y}
            width="29"
            height="18"
            rx="1"
            fill="#f1f5f9"
            stroke={INK}
            strokeOpacity="0.7"
            strokeWidth="0.8"
          />
          <path
            d={`M${x + 3} ${y + 15} C${x + 9} ${y + 9} ${x + 15} ${y + 13} ${x + 26} ${y + 7}`}
            stroke="#64748b"
            strokeWidth="0.8"
            strokeLinecap="round"
          />
          <circle
            cx={x + 10}
            cy={y + 7}
            r="2.6"
            stroke="#64748b"
            strokeWidth="0.8"
          />
          <rect x={x} y={y + 20} width="18" height="2" rx="1" fill="#cbd5e1" />
        </g>
      ))}
      <path
        d="M58.5 22 H61.5 M59.8 20.5 L61.5 22 L59.8 23.5"
        stroke="#3b82f6"
        strokeWidth="1.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M76 33.5 V39 M74.5 37.5 L76 39 L77.5 37.5"
        stroke="#3b82f6"
        strokeWidth="1.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="88" y="4" width="20" height="13" rx="3" fill={INK} />
      <rect x="92" y="2.5" width="7" height="3" rx="1" fill={INK} />
      <circle
        cx="98"
        cy="10.5"
        r="4.2"
        fill="#60a5fa"
        stroke="#ffffff"
        strokeWidth="1"
      />
      <circle cx="98" cy="10.5" r="1.6" fill="#1e3a8a" />
    </PictureArt>
  )
}
