import { useId } from "react";

/**
 * Reddit's full-colour mark (the orange circle with Snoo), as supplied directly.
 *
 * Unlike the other brand logos it carries its own colours and gradients, so
 * it ignores `currentColor`. Its gradient ids come from `useId`, because the
 * plugins page draws it twice: once in the grid and once in the footer.
 */
export function RedditLogo(props: React.SVGProps<SVGSVGElement>) {
	const id = useId();
	return (
		<svg viewBox="0 0 216 216" aria-hidden="true" {...props}>
			<defs>
				<radialGradient
					id={`${id}-face`}
					cx="169.75"
					cy="92.19"
					r="50.98"
					fx="169.75"
					fy="92.19"
					gradientTransform="matrix(1 0 0 .87 0 11.64)"
					gradientUnits="userSpaceOnUse"
				>
					<stop offset="0" stopColor="#feffff" />
					<stop offset=".4" stopColor="#feffff" />
					<stop offset=".51" stopColor="#f9fcfc" />
					<stop offset=".62" stopColor="#edf3f5" />
					<stop offset=".7" stopColor="#dee9ec" />
					<stop offset=".72" stopColor="#d8e4e8" />
					<stop offset=".76" stopColor="#ccd8df" />
					<stop offset=".8" stopColor="#c8d5dd" />
					<stop offset=".83" stopColor="#ccd6de" />
					<stop offset=".85" stopColor="#d8dbe2" />
					<stop offset=".88" stopColor="#ede3e9" />
					<stop offset=".9" stopColor="#ffebef" />
				</radialGradient>
				<radialGradient
					id={`${id}-ear-left`}
					cx="47.31"
					r="50.98"
					fx="47.31"
					href={`#${id}-face`}
				/>
				<radialGradient
					id={`${id}-head`}
					cx="109.61"
					cy="85.59"
					r="153.78"
					fx="109.61"
					fy="85.59"
					gradientTransform="matrix(1 0 0 .7 0 25.56)"
					href={`#${id}-face`}
				/>
				<radialGradient
					id={`${id}-eye-left`}
					cx="-6.01"
					cy="64.68"
					r="12.85"
					fx="-6.01"
					fy="64.68"
					gradientTransform="matrix(1.07 0 0 1.55 81.08 27.26)"
					gradientUnits="userSpaceOnUse"
				>
					<stop offset="0" stopColor="#f60" />
					<stop offset=".5" stopColor="#ff4500" />
					<stop offset=".7" stopColor="#fc4301" />
					<stop offset=".82" stopColor="#f43f07" />
					<stop offset=".92" stopColor="#e53812" />
					<stop offset="1" stopColor="#d4301f" />
				</radialGradient>
				<radialGradient
					id={`${id}-eye-right`}
					cx="-73.55"
					cy="64.68"
					r="12.85"
					fx="-73.55"
					fy="64.68"
					gradientTransform="matrix(-1.07 0 0 1.55 62.87 27.26)"
					href={`#${id}-eye-left`}
				/>
				<radialGradient
					id={`${id}-mouth`}
					cx="107.93"
					cy="166.96"
					r="45.3"
					fx="107.93"
					fy="166.96"
					gradientTransform="matrix(1 0 0 .66 0 57.4)"
					gradientUnits="userSpaceOnUse"
				>
					<stop offset="0" stopColor="#172e35" />
					<stop offset=".29" stopColor="#0e1c21" />
					<stop offset=".73" stopColor="#030708" />
					<stop offset="1" />
				</radialGradient>
				<radialGradient
					id={`${id}-antenna-tip`}
					cx="147.88"
					cy="32.94"
					r="39.77"
					fx="147.88"
					fy="32.94"
					gradientTransform="matrix(1 0 0 .98 0 .54)"
					href={`#${id}-face`}
				/>
				<radialGradient
					id={`${id}-antenna`}
					cx="131.31"
					cy="73.08"
					r="32.6"
					fx="131.31"
					fy="73.08"
					gradientUnits="userSpaceOnUse"
				>
					<stop offset=".48" stopColor="#7a9299" />
					<stop offset=".67" stopColor="#172e35" />
					<stop offset=".75" />
					<stop offset=".82" stopColor="#172e35" />
				</radialGradient>
			</defs>
			<path
				fill="#ff4500"
				d="M108 0C48.35 0 0 48.35 0 108c0 29.82 12.09 56.82 31.63 76.37l-20.57 20.57C6.98 209.029.87 216 15.64 216H108c59.65 0 108-48.35 108-108S167.65 0 108 0"
			/>
			<circle cx="169.22" cy="106.98" r="25.22" fill={`url(#${id}-face)`} />
			<circle cx="46.78" cy="106.98" r="25.22" fill={`url(#${id}-ear-left)`} />
			<ellipse cx="108.06" cy="128.64" fill={`url(#${id}-head)`} rx="72" ry="54" />
			<path
				fill={`url(#${id}-eye-left)`}
				d="M86.78 123.48c-.42 9.08-6.49 12.38-13.56 12.38s-12.46-4.93-12.04-14.01s6.49-15.02 13.56-15.02s12.46 7.58 12.04 16.66Z"
			/>
			<path
				fill={`url(#${id}-eye-right)`}
				d="M129.35 123.48c.42 9.08 6.49 12.38 13.56 12.38s12.46-4.93 12.04-14.01s-6.49-15.02-13.56-15.02s-12.46 7.58-12.04 16.66Z"
			/>
			<ellipse cx="79.63" cy="116.37" fill="#ffc49c" rx="2.8" ry="3.05" />
			<ellipse cx="146.21" cy="116.37" fill="#ffc49c" rx="2.8" ry="3.05" />
			<path
				fill={`url(#${id}-mouth)`}
				d="M108.06 142.92c-8.76 0-17.16.43-24.92 1.22c-1.33.13-2.17 1.51-1.65 2.74c4.35 10.39 14.61 17.69 26.57 17.69s22.23-7.3 26.57-17.69c.52-1.23-.33-2.61-1.65-2.74c-7.77-.79-16.16-1.22-24.92-1.22"
			/>
			<circle cx="147.49" cy="49.43" r="17.87" fill={`url(#${id}-antenna-tip)`} />
			<path
				fill={`url(#${id}-antenna)`}
				d="M107.8 76.92c-2.14 0-3.87-.89-3.87-2.27c0-16.01 13.03-29.04 29.04-29.04c2.14 0 3.87 1.73 3.87 3.87s-1.73 3.87-3.87 3.87c-11.74 0-21.29 9.55-21.29 21.29c0 1.38-1.73 2.27-3.87 2.27Z"
			/>
			<path
				fill="#842123"
				d="M62.82 122.65c.39-8.56 6.08-14.16 12.69-14.16c6.26 0 11.1 6.39 11.28 14.33c.17-8.88-5.13-15.99-12.05-15.99s-13.14 6.05-13.56 15.2s4.97 13.83 12.04 13.83h.52c-6.44-.16-11.3-4.79-10.91-13.2Zm90.48 0c-.39-8.56-6.08-14.16-12.69-14.16c-6.26 0-11.1 6.39-11.28 14.33c-.17-8.88 5.13-15.99 12.05-15.99c7.07 0 13.14 6.05 13.56 15.2s-4.97 13.83-12.04 13.83h-.52c6.44-.16 11.3-4.79 10.91-13.2Z"
			/>
		</svg>
	);
}
