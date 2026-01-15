"use client";

import { useState } from "react";
import { CommentComposer } from "@/components/chat-comments/comment-composer/comment-composer";
import { CommentItem } from "@/components/chat-comments/comment-item/comment-item";
import type { CommentData } from "@/components/chat-comments/comment-item/types";
import { CommentThread } from "@/components/chat-comments/comment-thread/comment-thread";
import type { CommentThreadData } from "@/components/chat-comments/comment-thread/types";
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

const fakeCommentsData: CommentData[] = [
	{
		id: 1,
		content: "This is a great response! @Alice Smith can you review?",
		contentRendered: "This is a great response! @Alice Smith can you review?",
		author: {
			id: "550e8400-e29b-41d4-a716-446655440002",
			displayName: "Bob Johnson",
			email: "bob.johnson@example.com",
			avatarUrl: null,
		},
		createdAt: new Date().toISOString(),
		updatedAt: new Date().toISOString(),
		isEdited: false,
		canEdit: true,
		canDelete: true,
	},
	{
		id: 2,
		content: "I checked this yesterday and it looks good.",
		contentRendered: "I checked this yesterday and it looks good.",
		author: {
			id: "550e8400-e29b-41d4-a716-446655440001",
			displayName: "Alice Smith",
			email: "alice@example.com",
			avatarUrl: null,
		},
		createdAt: new Date(Date.now() - 86400000).toISOString(),
		updatedAt: new Date(Date.now() - 3600000).toISOString(),
		isEdited: true,
		canEdit: false,
		canDelete: true,
	},
	{
		id: 3,
		content: "Thanks @Bob Johnson and @Alice Smith for the quick turnaround!",
		contentRendered: "Thanks @Bob Johnson and @Alice Smith for the quick turnaround!",
		author: {
			id: "550e8400-e29b-41d4-a716-446655440004",
			displayName: null,
			email: "david.wilson@example.com",
			avatarUrl: null,
		},
		createdAt: new Date(Date.now() - 3600000 * 3).toISOString(),
		updatedAt: new Date(Date.now() - 3600000 * 3).toISOString(),
		isEdited: false,
		canEdit: true,
		canDelete: false,
	},
];

const fakeThreadsData: CommentThreadData[] = [
	{
		id: 1,
		messageId: 101,
		content: "This is a great response! @Alice Smith can you review?",
		contentRendered: "This is a great response! @Alice Smith can you review?",
		author: {
			id: "550e8400-e29b-41d4-a716-446655440002",
			displayName: "Bob Johnson",
			email: "bob.johnson@example.com",
			avatarUrl: null,
		},
		createdAt: new Date(Date.now() - 3600000).toISOString(),
		updatedAt: new Date(Date.now() - 3600000).toISOString(),
		isEdited: false,
		canEdit: true,
		canDelete: true,
		replyCount: 2,
		replies: [
			{
				id: 2,
				content: "I checked this yesterday and it looks good.",
				contentRendered: "I checked this yesterday and it looks good.",
				author: {
					id: "550e8400-e29b-41d4-a716-446655440001",
					displayName: "Alice Smith",
					email: "alice@example.com",
					avatarUrl: null,
				},
				createdAt: new Date(Date.now() - 1800000).toISOString(),
				updatedAt: new Date(Date.now() - 1800000).toISOString(),
				isEdited: false,
				canEdit: false,
				canDelete: true,
			},
			{
				id: 3,
				content: "Thanks @Alice Smith!",
				contentRendered: "Thanks @Alice Smith!",
				author: {
					id: "550e8400-e29b-41d4-a716-446655440002",
					displayName: "Bob Johnson",
					email: "bob.johnson@example.com",
					avatarUrl: null,
				},
				createdAt: new Date(Date.now() - 900000).toISOString(),
				updatedAt: new Date(Date.now() - 900000).toISOString(),
				isEdited: false,
				canEdit: true,
				canDelete: true,
			},
		],
	},
	{
		id: 4,
		messageId: 101,
		content: "Can we also add some documentation for this feature?",
		contentRendered: "Can we also add some documentation for this feature?",
		author: {
			id: "550e8400-e29b-41d4-a716-446655440003",
			displayName: "Charlie Brown",
			email: "charlie@example.com",
			avatarUrl: null,
		},
		createdAt: new Date(Date.now() - 7200000).toISOString(),
		updatedAt: new Date(Date.now() - 7200000).toISOString(),
		isEdited: false,
		canEdit: false,
		canDelete: true,
		replyCount: 1,
		replies: [
			{
				id: 5,
				content: "Good idea @Charlie Brown, I'll create a ticket for that.",
				contentRendered: "Good idea @Charlie Brown, I'll create a ticket for that.",
				author: {
					id: "550e8400-e29b-41d4-a716-446655440002",
					displayName: "Bob Johnson",
					email: "bob.johnson@example.com",
					avatarUrl: null,
				},
				createdAt: new Date(Date.now() - 6000000).toISOString(),
				updatedAt: new Date(Date.now() - 6000000).toISOString(),
				isEdited: false,
				canEdit: true,
				canDelete: true,
			},
		],
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

				{/* Comment Thread Section */}
				<section className="space-y-4">
					<h2 className="text-xl font-semibold border-b pb-2">Comment Thread</h2>
					<p className="text-sm text-muted-foreground">
						Two top-level comments with replies. Click Reply to open composer. Click the replies count to collapse/expand.
					</p>

					<div className="max-w-lg space-y-6 rounded-lg border p-4">
						{fakeThreadsData.map((thread) => (
							<CommentThread
								key={thread.id}
								thread={thread}
								members={fakeMembersData}
								onCreateReply={(commentId, content) => alert(`Reply to ${commentId}: ${content}`)}
								onEditComment={(commentId) => alert(`Edit comment ${commentId}`)}
								onDeleteComment={(commentId) => alert(`Delete comment ${commentId}`)}
							/>
						))}
					</div>
				</section>

				{/* Comment Item Section */}
				<section className="space-y-4">
					<h2 className="text-xl font-semibold border-b pb-2">Comment Item (Standalone)</h2>
					<p className="text-sm text-muted-foreground">
						Individual comment components. Hover to see action menu.
					</p>

					<div className="max-w-lg space-y-4 rounded-lg border p-4">
						<CommentItem
							comment={fakeCommentsData[2]}
							onEdit={(id) => alert(`Edit comment ${id}`)}
							onDelete={(id) => alert(`Delete comment ${id}`)}
							onReply={(id) => alert(`Reply to comment ${id}`)}
						/>
					</div>
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
