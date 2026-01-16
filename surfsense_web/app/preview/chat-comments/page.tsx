"use client";

import { useState } from "react";
import { CommentComposer } from "@/components/chat-comments/comment-composer/comment-composer";
import { CommentItem } from "@/components/chat-comments/comment-item/comment-item";
import type { CommentData } from "@/components/chat-comments/comment-item/types";
import { CommentPanel } from "@/components/chat-comments/comment-panel/comment-panel";
import { CommentThread } from "@/components/chat-comments/comment-thread/comment-thread";
import type { CommentThreadData } from "@/components/chat-comments/comment-thread/types";
import { CommentTrigger } from "@/components/chat-comments/comment-trigger/comment-trigger";
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
	{
		id: 6,
		messageId: 101,
		content: "I think we should also consider edge cases here. What happens if the input is empty?",
		contentRendered: "I think we should also consider edge cases here. What happens if the input is empty?",
		author: {
			id: "550e8400-e29b-41d4-a716-446655440001",
			displayName: "Alice Smith",
			email: "alice@example.com",
			avatarUrl: null,
		},
		createdAt: new Date(Date.now() - 10800000).toISOString(),
		updatedAt: new Date(Date.now() - 10800000).toISOString(),
		isEdited: false,
		canEdit: false,
		canDelete: true,
		replyCount: 3,
		replies: [
			{
				id: 7,
				content: "Good point! We should add validation.",
				contentRendered: "Good point! We should add validation.",
				author: {
					id: "550e8400-e29b-41d4-a716-446655440002",
					displayName: "Bob Johnson",
					email: "bob.johnson@example.com",
					avatarUrl: null,
				},
				createdAt: new Date(Date.now() - 10000000).toISOString(),
				updatedAt: new Date(Date.now() - 10000000).toISOString(),
				isEdited: false,
				canEdit: true,
				canDelete: true,
			},
			{
				id: 8,
				content: "I'll handle the validation logic @Alice Smith",
				contentRendered: "I'll handle the validation logic @Alice Smith",
				author: {
					id: "550e8400-e29b-41d4-a716-446655440003",
					displayName: "Charlie Brown",
					email: "charlie@example.com",
					avatarUrl: null,
				},
				createdAt: new Date(Date.now() - 9500000).toISOString(),
				updatedAt: new Date(Date.now() - 9500000).toISOString(),
				isEdited: false,
				canEdit: false,
				canDelete: true,
			},
			{
				id: 9,
				content: "Thanks @Charlie Brown!",
				contentRendered: "Thanks @Charlie Brown!",
				author: {
					id: "550e8400-e29b-41d4-a716-446655440001",
					displayName: "Alice Smith",
					email: "alice@example.com",
					avatarUrl: null,
				},
				createdAt: new Date(Date.now() - 9000000).toISOString(),
				updatedAt: new Date(Date.now() - 9000000).toISOString(),
				isEdited: false,
				canEdit: false,
				canDelete: true,
			},
		],
	},
	{
		id: 10,
		messageId: 101,
		content: "The performance looks great in the benchmarks. Nice work everyone!",
		contentRendered: "The performance looks great in the benchmarks. Nice work everyone!",
		author: {
			id: "550e8400-e29b-41d4-a716-446655440005",
			displayName: "Emma Davis",
			email: "emma@example.com",
			avatarUrl: null,
		},
		createdAt: new Date(Date.now() - 14400000).toISOString(),
		updatedAt: new Date(Date.now() - 14400000).toISOString(),
		isEdited: false,
		canEdit: false,
		canDelete: true,
		replyCount: 0,
		replies: [],
	},
	{
		id: 11,
		messageId: 101,
		content: "Should we schedule a review meeting for this?",
		contentRendered: "Should we schedule a review meeting for this?",
		author: {
			id: "550e8400-e29b-41d4-a716-446655440004",
			displayName: null,
			email: "david.wilson@example.com",
			avatarUrl: null,
		},
		createdAt: new Date(Date.now() - 18000000).toISOString(),
		updatedAt: new Date(Date.now() - 18000000).toISOString(),
		isEdited: true,
		canEdit: true,
		canDelete: true,
		replyCount: 2,
		replies: [
			{
				id: 12,
				content: "Yes, let's do it tomorrow at 10am",
				contentRendered: "Yes, let's do it tomorrow at 10am",
				author: {
					id: "550e8400-e29b-41d4-a716-446655440002",
					displayName: "Bob Johnson",
					email: "bob.johnson@example.com",
					avatarUrl: null,
				},
				createdAt: new Date(Date.now() - 17000000).toISOString(),
				updatedAt: new Date(Date.now() - 17000000).toISOString(),
				isEdited: false,
				canEdit: true,
				canDelete: true,
			},
			{
				id: 13,
				content: "Works for me!",
				contentRendered: "Works for me!",
				author: {
					id: "550e8400-e29b-41d4-a716-446655440005",
					displayName: "Emma Davis",
					email: "emma@example.com",
					avatarUrl: null,
				},
				createdAt: new Date(Date.now() - 16000000).toISOString(),
				updatedAt: new Date(Date.now() - 16000000).toISOString(),
				isEdited: false,
				canEdit: false,
				canDelete: true,
			},
		],
	},
];

export default function ChatCommentsPreviewPage() {
	const [highlightedIndex, setHighlightedIndex] = useState(0);
	const [selectedMember, setSelectedMember] = useState<MemberOption | null>(null);
	const [submittedContent, setSubmittedContent] = useState<string | null>(null);
	const [isPanelOpen, setIsPanelOpen] = useState(false);
	const [isEmptyPanelOpen, setIsEmptyPanelOpen] = useState(false);

	return (
		<div className="min-h-screen bg-background p-8">
			<div className="mx-auto max-w-6xl space-y-12">
				<div>
					<h1 className="text-2xl font-bold">Chat Comments UI Preview</h1>
					<p className="text-muted-foreground">
						Preview page for chat comments components with fake data
					</p>
				</div>

				{/* Full Integration Simulation */}
				<section className="space-y-6">
					<div>
						<h2 className="text-xl font-semibold border-b pb-2">🎯 Full Integration Simulation</h2>
						<p className="text-sm text-muted-foreground">
							Two scenarios: no comments (hover to see trigger) and with comments (always visible).
						</p>
					</div>

					{/* Scenario 1: No comments yet */}
					<div className="space-y-2">
						<h3 className="text-sm font-medium text-muted-foreground">No comments yet — hover to see trigger, click to add first comment</h3>
						<div className="group flex items-start gap-2">
							<div className="max-w-2xl rounded-lg border bg-muted/20 p-4">
								<div className="space-y-2">
									<div className="flex items-center gap-2">
										<div className="size-8 rounded-full bg-gradient-to-br from-green-500 to-teal-600" />
										<span className="font-medium">AI Assistant</span>
									</div>
									<p className="text-sm leading-relaxed">
										This is an AI response with no comments yet. Hover over this message to reveal the comment trigger icon on the right. Click to open the panel and add the first comment.
									</p>
								</div>
							</div>
							<CommentTrigger 
								commentCount={0} 
								isOpen={isEmptyPanelOpen} 
								onClick={() => setIsEmptyPanelOpen(!isEmptyPanelOpen)} 
							/>
							{isEmptyPanelOpen && (
								<CommentPanel
									messageId={102}
									threads={[]}
									members={fakeMembersData}
									onCreateComment={(content) => alert(`Create first comment: ${content}`)}
									onCreateReply={() => {}}
									onEditComment={() => {}}
									onDeleteComment={() => {}}
									maxHeight={300}
								/>
							)}
						</div>
					</div>

					{/* Scenario 2: Has comments */}
					<div className="space-y-2">
						<h3 className="text-sm font-medium text-muted-foreground">Has comments — trigger always visible, click to toggle panel</h3>
						<div className="group flex items-start gap-2">
							<div className="max-w-2xl rounded-lg border bg-muted/20 p-4">
								<div className="space-y-2">
									<div className="flex items-center gap-2">
										<div className="size-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600" />
										<span className="font-medium">AI Assistant</span>
									</div>
									<p className="text-sm leading-relaxed">
										Based on my analysis, the quarterly revenue increased by 15% compared to the previous period. 
										The main drivers were the expansion into new markets and improved customer retention rates. 
										I recommend focusing on the following areas for continued growth...
									</p>
								</div>
							</div>
							<CommentTrigger 
								commentCount={fakeThreadsData.length} 
								isOpen={isPanelOpen} 
								onClick={() => setIsPanelOpen(!isPanelOpen)} 
							/>
							{isPanelOpen && (
								<CommentPanel
									messageId={101}
									threads={fakeThreadsData.slice(0, 2)}
									members={fakeMembersData}
									onCreateComment={(content) => alert(`Create comment: ${content}`)}
									onCreateReply={(id, content) => alert(`Reply to ${id}: ${content}`)}
									onEditComment={(id) => alert(`Edit ${id}`)}
									onDeleteComment={(id) => alert(`Delete ${id}`)}
									maxHeight={350}
								/>
							)}
						</div>
					</div>
				</section>

				{/* Comment Composer Section */}
				<section className="space-y-4">
					<h2 className="text-xl font-semibold border-b pb-2">Comment Composer</h2>
					<p className="text-sm text-muted-foreground">
						Type @ to trigger mention picker. Use Tab/Shift+Tab/Arrow keys to navigate, Enter to
						select.
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

				{/* Comment Trigger Section */}
				<section className="space-y-4">
					<h2 className="text-xl font-semibold border-b pb-2">Comment Trigger</h2>
					<p className="text-sm text-muted-foreground">
						Toggle button on AI messages. Clicking opens/closes the comment panel.
					</p>

					<div className="flex items-center gap-8">
						<div className="space-y-2">
							<h3 className="text-sm font-medium">No comments yet</h3>
							<p className="text-xs text-muted-foreground">Hidden until hover</p>
							<div className="group flex items-center gap-2 rounded-lg border bg-muted/30 p-4">
								<span className="text-sm">AI response...</span>
								<CommentTrigger commentCount={0} isOpen={false} onClick={() => {}} />
							</div>
						</div>

						<div className="space-y-2">
							<h3 className="text-sm font-medium">5 comments exist</h3>
							<p className="text-xs text-muted-foreground">Always visible with count</p>
							<div className="group flex items-center gap-2 rounded-lg border bg-muted/30 p-4">
								<span className="text-sm">AI response...</span>
								<CommentTrigger commentCount={5} isOpen={false} onClick={() => {}} />
							</div>
						</div>

						<div className="space-y-2">
							<h3 className="text-sm font-medium">Panel is open</h3>
							<p className="text-xs text-muted-foreground">Active/pressed state</p>
							<div className="group flex items-center gap-2 rounded-lg border bg-muted/30 p-4">
								<span className="text-sm">AI response...</span>
								<CommentTrigger commentCount={3} isOpen={true} onClick={() => {}} />
							</div>
						</div>
					</div>
				</section>

				{/* Comment Panel Section */}
				<section className="space-y-4">
					<h2 className="text-xl font-semibold border-b pb-2">Comment Panel</h2>
					<p className="text-sm text-muted-foreground">
						Full panel with scrollable threads and composer. Shows alongside AI responses.
					</p>

					<div className="flex gap-8">
						<div className="space-y-2">
							<h3 className="text-sm font-medium">With comments</h3>
							<CommentPanel
								messageId={101}
								threads={fakeThreadsData}
								members={fakeMembersData}
								onCreateComment={(content) => alert(`Create: ${content}`)}
								onCreateReply={(id, content) => alert(`Reply ${id}: ${content}`)}
								onEditComment={(id) => alert(`Edit ${id}`)}
								onDeleteComment={(id) => alert(`Delete ${id}`)}
							/>
						</div>

						<div className="space-y-2">
							<h3 className="text-sm font-medium">Empty state</h3>
							<CommentPanel
								messageId={102}
								threads={[]}
								members={fakeMembersData}
								onCreateComment={(content) => alert(`Create: ${content}`)}
								onCreateReply={(id, content) => alert(`Reply ${id}: ${content}`)}
								onEditComment={(id) => alert(`Edit ${id}`)}
								onDeleteComment={(id) => alert(`Delete ${id}`)}
							/>
						</div>

						<div className="space-y-2">
							<h3 className="text-sm font-medium">Loading</h3>
							<CommentPanel
								messageId={103}
								threads={[]}
								members={[]}
								isLoading
								onCreateComment={() => {}}
								onCreateReply={() => {}}
								onEditComment={() => {}}
								onDeleteComment={() => {}}
							/>
						</div>
					</div>
				</section>

				{/* Comment Thread Section */}
				<section className="space-y-4">
					<h2 className="text-xl font-semibold border-b pb-2">Comment Thread</h2>
					<p className="text-sm text-muted-foreground">
						Two top-level comments with replies. Click Reply to open composer. Click the replies
						count to collapse/expand.
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
					<h2 className="text-xl font-semibold border-b pb-2">
						Member Mention Picker (Standalone)
					</h2>

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
