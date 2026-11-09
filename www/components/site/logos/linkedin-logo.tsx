/** LinkedIn's full-colour mark: the white "in" on its blue square. Supplied directly. */
export function LinkedinLogo(props: React.SVGProps<SVGSVGElement>) {
	return (
		<svg viewBox="0 0 512 512" aria-hidden="true" {...props}>
			<path
				fill="#007ebb"
				fillRule="evenodd"
				d="M56.9 512h398.2c31.4 0 56.9-25.5 56.9-56.9V56.9C512 25.5 486.5 0 455.1 0H56.9C25.5 0 0 25.5 0 56.9v398.2C0 486.5 25.5 512 56.9 512"
			/>
			<path
				fill="#fff"
				fillRule="evenodd"
				d="M440.9 440.9h-76V311.5c0-35.5-13.5-55.3-41.6-55.3c-30.5 0-46.5 20.6-46.5 55.3v129.4h-73.2V194.4h73.2v33.2s22-40.7 74.3-40.7s89.7 31.9 89.7 98v156zM116.3 162.1c-24.9 0-45.2-20.4-45.2-45.5s20.2-45.5 45.2-45.5s45.1 20.4 45.1 45.5s-20.2 45.5-45.1 45.5M78.5 440.9h76.4V194.4H78.5z"
			/>
		</svg>
	);
}
