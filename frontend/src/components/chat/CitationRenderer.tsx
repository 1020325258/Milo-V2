import { BookOpen } from 'lucide-react';

import type { CitationData } from './CitationModal';

interface CitationRendererProps {
	fileName: string;
	onClick: () => void;
}

/**
 * Inline citation marker component.
 *
 * Renders a clickable blue badge that represents a knowledge citation
 * in the LLM's response. When clicked, it opens the citation detail modal.
 */
export function CitationRenderer({ fileName, onClick }: CitationRendererProps) {
	return (
		<button
			type="button"
			className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded cursor-pointer transition-colors"
			onClick={onClick}
			title={`查看来源: ${fileName}`}
		>
			<BookOpen className="size-3" />
			<span>来源：{fileName}</span>
		</button>
	);
}

/**
 * Parse citation references from markdown text.
 *
 * Extracts citation markers like [来源：filename] from the text
 * and returns the parsed citations and cleaned text.
 *
 * @param text - The markdown text containing citation markers
 * @returns Object with parsed citations and cleaned text
 */
export function parseCitations(text: string): {
	citations: CitationData[];
	cleanText: string;
} {
	const citations: CitationData[] = [];
	// Match [来源：filename] pattern
	const citationRegex = /\[来源：([^\]]+)\]/g;

	let match: RegExpExecArray | null;
	// biome-ignore lint/suspicious/noAssignInExpressions: needed for regex parsing
	while ((match = citationRegex.exec(text)) !== null) {
		citations.push({
			fileName: match[1],
			title: '',
			content: '',
			paths: [],
		});
	}

	return { citations, cleanText: text };
}

/**
 * Parse the citation source list from the end of the message.
 *
 * Extracts the "引用来源：" section and parses individual citation entries.
 *
 * @param text - The full message text
 * @returns Array of parsed citation data
 */
export function parseCitationList(text: string): CitationData[] {
	const citations: CitationData[] = [];

	// Find the citation list section
	const listMatch = text.match(/\*\*引用来源：\*\*\n([\s\S]*?)$/);
	if (!listMatch) return citations;

	const listText = listMatch[1];
	// Match entries like "1. filename - title"
	const entryRegex = /\d+\.\s+(.+?)(?:\s+-\s+(.+))?$/gm;

	let match: RegExpExecArray | null;
	// biome-ignore lint/suspicious/noAssignInExpressions: needed for regex parsing
	while ((match = entryRegex.exec(listText)) !== null) {
		citations.push({
			fileName: match[1].trim(),
			title: match[2]?.trim() || '',
			content: '',
			paths: [],
		});
	}

	return citations;
}
