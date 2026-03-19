import type { BaseLayoutProps } from "fumadocs-ui/layouts/shared";
import Image from "next/image";
export const baseOptions: BaseLayoutProps = {
	nav: {
		title: (
			<>
				<Image src="/icon-128.svg" alt="NeoNote" width={24} height={24} />
				NeoNote Docs
			</>
		),
	},
	githubUrl: "https://github.com/MODSetter/NeoNote",
};
