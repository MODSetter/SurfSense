import { Logo } from "@/components/Logo";

export function FooterNew() {
	return (
		<div className="border-t border-neutral-100 dark:border-white/[0.1] px-8 py-20 bg-white dark:bg-neutral-950 w-full relative overflow-hidden">
			<div className="max-w-7xl mx-auto text-sm text-neutral-500 flex sm:flex-row flex-col justify-between items-start  md:px-8">
				<div>
					<div className="mr-0 md:mr-4  md:flex mb-4">
						<Logo className="h-6 w-6 rounded-md mr-2" />
						<span className="dark:text-white/90 text-gray-800 text-lg font-bold">SurfSense</span>
					</div>

					<div className="mt-2 ml-2">
						&copy; SurfSense {new Date().getFullYear()}. All rights reserved.
					</div>
				</div>
			</div>
			<p className="text-center mt-20 text-5xl md:text-9xl lg:text-[12rem] xl:text-[13rem] font-bold bg-clip-text text-transparent bg-gradient-to-b from-neutral-50 dark:from-neutral-950 to-neutral-200 dark:to-neutral-800 inset-x-0">
				SurfSense
			</p>
		</div>
	);
}
