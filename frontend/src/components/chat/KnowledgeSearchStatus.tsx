import { BookOpen, Loader2, Search, AlertCircle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';

export type KnowledgeSearchState = 'idle' | 'searching' | 'completed' | 'failed';

interface KnowledgeSearchStatusProps {
	state: KnowledgeSearchState;
	resultCount?: number;
}

/**
 * Component for displaying knowledge search status in the chat interface.
 *
 * Shows different states:
 * - searching: "正在检索知识库..." with loading spinner
 * - completed: "已检索到 N 条相关知识" with success icon
 * - failed: "知识库检索失败" with error icon
 * - idle: nothing rendered
 */
export function KnowledgeSearchStatus({
	state,
	resultCount = 0,
}: KnowledgeSearchStatusProps) {
	if (state === 'idle') return null;

	return (
		<div className="flex items-center gap-2 px-4 py-2">
			<Badge variant="outline" className="gap-1.5">
				{state === 'searching' && (
					<>
						<Loader2 className="size-3 animate-spin" />
						<span>正在检索知识库...</span>
					</>
				)}
				{state === 'completed' && (
					<>
						<BookOpen className="size-3" />
						<span>已检索到 {resultCount} 条相关知识</span>
					</>
				)}
				{state === 'failed' && (
					<>
						<AlertCircle className="size-3 text-destructive" />
						<span>知识库检索失败，将基于通用知识回答</span>
					</>
				)}
			</Badge>
		</div>
	);
}
