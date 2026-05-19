const USER_AVATAR_COLORS = [
	"#6366f1",
	"#8b5cf6",
	"#a855f7",
	"#d946ef",
	"#ec4899",
	"#f43f5e",
	"#ef4444",
	"#f97316",
	"#eab308",
	"#84cc16",
	"#22c55e",
	"#14b8a6",
	"#06b6d4",
	"#0ea5e9",
	"#3b82f6",
];

export function getUserAvatarColor(email: string): string {
	let hash = 0;
	for (let i = 0; i < email.length; i++) {
		hash = email.charCodeAt(i) + ((hash << 5) - hash);
	}
	return USER_AVATAR_COLORS[Math.abs(hash) % USER_AVATAR_COLORS.length];
}

export function getUserInitials(email: string): string {
	const name = email.split("@")[0];
	const parts = name.split(/[._-]/);
	if (parts.length >= 2 && parts[0]?.[0] && parts[1]?.[0]) {
		return (parts[0][0] + parts[1][0]).toUpperCase();
	}
	return name.slice(0, 2).toUpperCase();
}
