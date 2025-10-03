import { Sliders, Users, Workflow } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export function FeaturesCards() {
	return (
		<section className="py-2 md:py-8 dark:bg-transparent">
			<div className="@container mx-auto max-w-7xl">
				<div className="text-center">
					<h2 className="text-balance text-4xl font-semibold lg:text-5xl">
						Your Team's AI-Powered Knowledge Hub
					</h2>
					<p className="mt-4">
						Powerful features designed to enhance collaboration, boost productivity, and streamline
						your workflow.
					</p>
				</div>
				<div className="@min-4xl:max-w-full @min-4xl:grid-cols-3 mx-auto mt-8 grid max-w-sm gap-6 *:text-center md:mt-16">
					<Card className="group shadow-black-950/5">
						<CardHeader className="pb-3">
							<CardDecorator>
								<Workflow className="size-6" aria-hidden />
							</CardDecorator>

							<h3 className="mt-6 font-medium">Streamlined Workflow</h3>
						</CardHeader>

						<CardContent>
							<p className="text-sm">
								Centralize all your knowledge and resources in one intelligent workspace. Find what
								you need instantly and accelerate decision-making.
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
							<p className="text-sm">
								Work together effortlessly with real-time collaboration tools that keep your entire
								team aligned.
							</p>
						</CardContent>
					</Card>

					<Card className="group shadow-black-950/5">
						<CardHeader className="pb-3">
							<CardDecorator>
								<Sliders className="size-6" aria-hidden />
							</CardDecorator>

							<h3 className="mt-6 font-medium">Fully Customizable</h3>
						</CardHeader>

						<CardContent>
							<p className="text-sm">
								Choose from 100+ leading LLMs and seamlessly call any model on demand.
							</p>
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
