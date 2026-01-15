"use client";

import { useState } from "react";
import { CommentComposer } from "@/components/chat-comments/comment-composer/comment-composer";
import { MemberMentionPicker } from "@/components/chat-comments/member-mention-picker/member-mention-picker";
import type { MemberOption } from "@/components/chat-comments/member-mention-picker/types";

const fakeMembersData: MemberOption[] = [
	{
		id: "550e8400-e29b-41d4-a716-446655440001",
		displayName: "Alice Smith",
		email: "alice@example.com",
		avatarUrl: null,
	},
	{
		id: "550e8400-e29b-41d4-a716-446655440002",
		displayName: "Bob Johnson",
		email: "bob.johnson@example.com",
		avatarUrl: null,
	},
	{
		id: "550e8400-e29b-41d4-a716-446655440003",
		displayName: "Charlie Brown",
		email: "charlie@example.com",
		avatarUrl: null,
	},
	{
		id: "550e8400-e29b-41d4-a716-446655440004",
		displayName: null,
		email: "david.wilson@example.com",
		avatarUrl: null,
	},
	{
		id: "550e8400-e29b-41d4-a716-446655440005",
		displayName: "Emma Davis",
		email: "emma@example.com",
		avatarUrl: null,
	},
];

export default function ChatCommentsPreviewPage() {
	const [highlightedIndex, setHighlightedIndex] = useState(0);
	const [selectedMember, setSelectedMember] = useState<MemberOption | null>(null);
	const [submittedContent, setSubmittedContent] = useState<string | null>(null);

	return (
		<div className="min-h-screen bg-background p-8">
			<div className="mx-auto max-w-4xl space-y-12">
				<div>
					<h1 className="text-2xl font-bold">Chat Comments UI Preview</h1>
					<p className="text-muted-foreground">
						Preview page for chat comments components with fake data
					</p>
				</div>

				{/* Comment Composer Section */}
				<section className="space-y-4">
					<h2 className="text-xl font-semibold border-b pb-2">Comment Composer</h2>
					<p className="text-sm text-muted-foreground">
						Type @ to trigger mention picker. Use Tab/Shift+Tab/Arrow keys to navigate, Enter to select.
					</p>

					<div className="max-w-md rounded-lg border p-4">
						<CommentComposer
							members={fakeMembersData}
							placeholder="Write a comment... (try typing @)"
							onSubmit={(content) => setSubmittedContent(content)}
							onCancel={() => setSubmittedContent(null)}
							autoFocus
						/>
					</div>

					{submittedContent && (
						<div className="max-w-md rounded-md bg-muted p-3 text-sm">
							<span className="font-medium">Submitted content: </span>
							<code className="block mt-1 rounded bg-background p-2 whitespace-pre-wrap">
								{submittedContent}
							</code>
						</div>
					)}
				</section>

				{/* Member Mention Picker Section */}
				<section className="space-y-4">
					<h2 className="text-xl font-semibold border-b pb-2">Member Mention Picker (Standalone)</h2>

					<div className="grid gap-8 md:grid-cols-2">
						<div className="space-y-4">
							<h3 className="text-lg font-medium">After typing @</h3>
							<p className="text-sm text-muted-foreground">Shows all members</p>
							<div className="w-72 rounded-lg border bg-popover shadow-lg">
								<MemberMentionPicker
									members={fakeMembersData}
									query=""
									highlightedIndex={highlightedIndex}
									onSelect={(member) => setSelectedMember(member)}
									onHighlightChange={setHighlightedIndex}
								/>
							</div>
							{selectedMember && (
								<div className="rounded-md bg-muted p-3 text-sm">
									<span className="font-medium">Selected: </span>
									<code className="rounded bg-background px-1">
										@[{selectedMember.id.slice(0, 8)}...]
									</code>
								</div>
							)}
						</div>

						<div className="space-y-4">
							<h3 className="text-lg font-medium">After typing @ali</h3>
							<p className="text-sm text-muted-foreground">Filtered to matching members</p>
							<div className="w-72 rounded-lg border bg-popover shadow-lg">
								<MemberMentionPicker
									members={fakeMembersData}
									query="ali"
									highlightedIndex={0}
									onSelect={() => {}}
									onHighlightChange={() => {}}
								/>
							</div>
						</div>

						<div className="space-y-4">
							<h3 className="text-lg font-medium">Loading State</h3>
							<p className="text-sm text-muted-foreground">While fetching members</p>
							<div className="w-72 rounded-lg border bg-popover shadow-lg">
								<MemberMentionPicker
									members={[]}
									query=""
									highlightedIndex={0}
									isLoading={true}
									onSelect={() => {}}
									onHighlightChange={() => {}}
								/>
							</div>
						</div>

						<div className="space-y-4">
							<h3 className="text-lg font-medium">No Results</h3>
							<p className="text-sm text-muted-foreground">After typing @xyz (no match)</p>
							<div className="w-72 rounded-lg border bg-popover shadow-lg">
								<MemberMentionPicker
									members={fakeMembersData}
									query="xyz"
									highlightedIndex={0}
									onSelect={() => {}}
									onHighlightChange={() => {}}
								/>
							</div>
						</div>
					</div>
				</section>
			</div>
		</div>
	);
}
