import type { TaskContext } from '@agentscope-ai/agentscope/state';
import { Toolbox } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { ChatContent } from '@/components/chat/ChatContent.tsx';
import { TaskPanel } from '@/components/chat/TaskPanel';
import { WorkspaceDrawer } from '@/components/drawer/WorkspaceDrawer.tsx';
import { Button } from '@/components/ui/button';
import { useMessages } from '@/hooks/useMessages';
import { useSessions } from '@/hooks/useSessions';
import { useWorkspace } from '@/hooks/useWorkspace.ts';

interface ChatViewportProps {
	/**
	 * The agent that owns the session being viewed. May be the
	 * user-facing leader agent or — when drilled into a team member
	 * via the URL's `:memberId` slot — a worker agent.
	 */
	agentId: string | null;
	/**
	 * The session whose messages and workspace drive every control
	 * rendered here.
	 */
	sessionId: string | null;
	/**
	 * Optional hook invoked when a team membership change arrives on
	 * this viewport's SSE stream. The outer page owns the session list
	 * that backs the team sidebar, so it must be told to refetch too;
	 * passing this callback wires that signal up.
	 */
	onTeamUpdated?: () => void;
}

/**
 * The right-hand main panel of the chat page — every UI element that
 * operates on a single `(agentId, sessionId)` pair lives here:
 * message stream, workspace drawer, and the team sidebar.
 *
 * Self-contained by design. The outer page passes in the
 * `(agentId, sessionId)` it wants displayed (which may be the leader
 * session or a focused team member's session) and this component
 * does the rest — fetching the session view, syncing local UI state
 * with it, and writing changes back to the same session. Switching
 * between leader and member is just a prop change; no internal
 * branching is needed.
 *
 * @param agentId - The agent to operate on. `null` while no agent is
 *   selected yet (renders an empty / disabled state).
 * @param sessionId - The session to operate on. `null` while no
 *   session is selected yet.
 * @returns The right-side main JSX of the chat page.
 */
export function ChatViewport({ agentId, sessionId, onTeamUpdated }: ChatViewportProps) {
	const { sessions, refetch: refetchSessions } = useSessions(agentId);

	// When the viewport agent differs from the outer page's selected
	// agent (i.e. user drilled into a team member), `refetchSessions`
	// only refreshes the member's session list. The team sidebar is
	// driven by the leader's session list owned by the outer page, so
	// we also fire the parent's refetch to keep that in sync.
	const handleTeamUpdated = useCallback(() => {
		refetchSessions();
		onTeamUpdated?.();
	}, [refetchSessions, onTeamUpdated]);

	const [tasksContext, setTasksContext] = useState<TaskContext | null>(null);

	const handleStateUpdated = useCallback((value: Record<string, unknown>) => {
		if (value.tasks_context) {
			setTasksContext(value.tasks_context as TaskContext);
		}
		// TODO: handle permission_context updates when permission UI is built
	}, []);

	const { msgs, streaming, connected, send, onUserConfirm } = useMessages(agentId, sessionId, {
		onTeamUpdated: handleTeamUpdated,
		onStateUpdated: handleStateUpdated,
	});
	const {
		mcps,
		loading: mcpsLoading,
		addMcps,
		removeMcp,
		skills,
		skillsLoading,
		addSkill,
		removeSkill,
	} = useWorkspace(agentId, sessionId);

	const view = sessions.find((v) => v.session.id === sessionId) ?? null;

	// ChatViewport keeps its own `useSessions(agentId)` instance (the
	// outer page has a separate one). Its built-in fetch only fires on
	// `agentId` change, so when the outer page creates a new session
	// under the same agent, this list doesn't auto-refresh. Without
	// this refetch, `view` would stay `null` for the brand-new session
	// id and every effect below would early-return on `!view`.
	useEffect(() => {
		if (!sessionId) return;
		if (view) return;
		refetchSessions();
	}, [sessionId, view, refetchSessions]);

	// Sync tasksContext from the session snapshot. Real-time updates
	// arrive via the CustomEvent(name="state_updated") → the
	// onStateUpdated callback above. We always mirror the snapshot
	// (including clearing to null when the session is gone or has no
	// tasks yet) so that switching sessions doesn't leak stale tasks
	// from the previous one.
	useEffect(() => {
		if (!view) {
			setTasksContext(null);
			return;
		}
		const tc = (view.session.state as Record<string, unknown>)?.tasks_context as
			| TaskContext
			| undefined;
		setTasksContext(tc ?? null);
	}, [view]);

	return (
		<>
			<main className="flex size-full">
				<div className="flex flex-col flex-1 min-h-0 p-2">
					<div className="flex flex-1 justify-center min-h-0 overflow-hidden relative [--chat-content-w:36rem]">
						<TaskPanel
							className="absolute left-0 top-0 h-full max-w-[calc(50%-var(--chat-content-w)/2)]"
							tasksContext={tasksContext}
						/>
						<ChatContent
							className={'max-w-[var(--chat-content-w)] w-full'}
							msgs={msgs}
							sending={streaming}
							disabled={!sessionId}
							connected={connected}
							allowedInputTypes={['text', 'image', 'file']}
							onSend={send}
							onUserConfirm={onUserConfirm}
							fileProcessor={async (file) => {
								const filePath = (file as File & { path?: string }).path;
								if (filePath) {
									return {
										id: crypto.randomUUID(),
										type: 'data' as const,
										source: {
											type: 'url' as const,
											url: `file://${filePath}`,
											media_type: file.type || 'application/octet-stream',
										},
										name: file.name,
									};
								}
								if (file.type === 'text/plain') {
									const text = await file.text();
									return {
										id: crypto.randomUUID(),
										type: 'text' as const,
										text: `[File: ${file.name}]\n${text}`,
									};
								}
								const buffer = await file.arrayBuffer();
								const bytes = new Uint8Array(buffer);
								let binary = '';
								for (let i = 0; i < bytes.byteLength; i++) {
									binary += String.fromCharCode(bytes[i]);
								}
								const base64 = btoa(binary);
								return {
									id: crypto.randomUUID(),
									type: 'data' as const,
									source: {
										type: 'base64' as const,
										media_type: file.type || 'application/octet-stream',
										data: base64,
									},
									name: file.name,
								};
							}}
						/>
					</div>
				</div>
				<div className="flex flex-col h-full gap-2 p-2">
					<WorkspaceDrawer
						mcps={mcps}
						loading={mcpsLoading}
						onAdd={addMcps}
						onRemove={removeMcp}
						skills={skills}
						skillsLoading={skillsLoading}
						onAddSkill={addSkill}
						onRemoveSkill={removeSkill}
					>
						<Button size="icon-sm" variant="ghost">
							<Toolbox />
						</Button>
					</WorkspaceDrawer>
				</div>
			</main>
		</>
	);
}
