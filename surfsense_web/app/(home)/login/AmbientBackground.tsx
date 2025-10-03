"use client";

export const AmbientBackground = () => {
	return (
		<div className="pointer-events-none absolute left-0 top-0 z-0 h-screen w-screen">
			<div
				style={{
					transform: "translateY(-350px) rotate(-45deg)",
					width: "560px",
					height: "1380px",
					background:
						"radial-gradient(68.54% 68.72% at 55.02% 31.46%, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.02) 50%, rgba(59, 130, 246, 0) 100%)",
				}}
				className="absolute left-0 top-0"
			/>
			<div
				style={{
					transform: "rotate(-45deg) translate(5%, -50%)",
					transformOrigin: "top left",
					width: "240px",
					height: "1380px",
					background:
						"radial-gradient(50% 50% at 50% 50%, rgba(59, 130, 246, 0.06) 0%, rgba(59, 130, 246, 0.02) 80%, transparent 100%)",
				}}
				className="absolute left-0 top-0"
			/>
			<div
				style={{
					position: "absolute",
					borderRadius: "20px",
					transform: "rotate(-45deg) translate(-180%, -70%)",
					transformOrigin: "top left",
					width: "240px",
					height: "1380px",
					background:
						"radial-gradient(50% 50% at 50% 50%, rgba(59, 130, 246, 0.04) 0%, rgba(59, 130, 246, 0.02) 80%, transparent 100%)",
				}}
				className="absolute left-0 top-0"
			/>
		</div>
	);
};
