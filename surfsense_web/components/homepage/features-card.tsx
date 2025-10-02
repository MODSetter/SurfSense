import { Sliders, Users, Workflow } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export function Features() {
	return (
		<section className="py-2 md:py-8 dark:bg-transparent">
			<div className="@container mx-auto max-w-5xl">
				{/* <div className="text-center">
                    <h2 className="text-balance text-4xl font-semibold lg:text-5xl">Built to cover your needs</h2>
                    <p className="mt-4">Libero sapiente aliquam quibusdam aspernatur, praesentium iusto repellendus.</p>
                </div> */}
				<div className="@min-4xl:max-w-full @min-4xl:grid-cols-3 mx-auto mt-8 grid max-w-sm gap-6 *:text-center md:mt-16">
					<Card className="group shadow-black-950/5">
						<CardHeader className="pb-3">
							<CardDecorator>
								<Sliders className="size-6" aria-hidden />
							</CardDecorator>

							<h3 className="mt-6 font-medium">Customizable</h3>
						</CardHeader>

						<CardContent>
							<p className="text-sm">Customize your research agent to your specific needs.</p>
						</CardContent>
					</Card>

					<Card className="group shadow-black-950/5">
						<CardHeader className="pb-3">
							<CardDecorator>
								<Workflow className="size-6" aria-hidden />
							</CardDecorator>

							<h3 className="mt-6 font-medium">Streamline your workflow</h3>
						</CardHeader>

						<CardContent>
							<p className="text-sm">
								Pull all your knowledge into one place, so you can find what matters and get things
								done faster.
							</p>
						</CardContent>
					</Card>

					<Card className="group shadow-black-950/5">
						<CardHeader className="pb-3">
							<CardDecorator>
								<Users className="size-6" aria-hidden />
							</CardDecorator>

							<h3 className="mt-6 font-medium">Seamless Collaboration</h3>
						</CardHeader>

						<CardContent>
							<p className="text-sm">Make your company and personal content collaborative.</p>
						</CardContent>
					</Card>
				</div>
			</div>
		</section>
	);
}

const CardDecorator = ({ children }: { children: ReactNode }) => (
	<div
		aria-hidden
		className="relative mx-auto size-36 [mask-image:radial-gradient(ellipse_50%_50%_at_50%_50%,#000_70%,transparent_100%)]"
	>
		<div className="absolute inset-0 [--border:black] dark:[--border:white] bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:24px_24px] opacity-10" />
		<div className="bg-background absolute inset-0 m-auto flex size-12 items-center justify-center border-t border-l">
			{children}
		</div>
	</div>
);
