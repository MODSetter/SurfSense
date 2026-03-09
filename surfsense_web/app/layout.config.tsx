import Image from "next/image";
import type { BaseLayoutProps } from "fumadocs-ui/layouts/shared";
export const baseOptions: BaseLayoutProps = {
	nav: {
		title: (
			<>
				<Image
					src="/icon-128.svg"
					alt="SurfSense"
					width={24}
					height={24}
					className="dark:invert"
				/>
				SurfSense Docs
			</>
		),
	},
	githubUrl: "https://github.com/MODSetter/SurfSense",
};
