import { BookOpen } from 'lucide-react';

import type { CitationData } from './CitationModal';

interface CitationRendererProps {
	fileName: string;
	onClick: () => void;
}

/**
 * Inline citation marker component.
 *
 * Renders a subtle, clickable badge that represents a knowledge citation
 * in the LLM's response. Styled with gray tones and smaller font to
 * distinguish from main content without being distracting.
 */
export function CitationRenderer({ fileName, onClick }: CitationRendererProps) {
	return (
		<button
			type="button"
			className="inline-flex items-center gap-0.5 px-1 py-0.5 text-[10px] leading-tight font-normal text-muted-foreground/70 hover:text-muted-foreground bg-muted/50 hover:bg-muted rounded-sm cursor-pointer transition-colors align-middle"
			onClick={onClick}
			title={`查看来源: ${fileName}`}
		>
			<BookOpen className="size-2.5" />
			<span>{fileName}</span>
		</button>
	);
}

/**
 * Parse citation references from markdown text.
 *
 * Extracts citation markers like [filename.md] from the text
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
	// Match [filename] pattern (not [来源：xxx] or [chunk-xxx])
	const citationRegex = /\[([^\]]+\.(md|pdf|doc|docx|txt))\]/g;

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
 * Parse the citation reference list from the end of the message.
 *
 * Extracts the "### References" section and parses individual citation entries.
 *
 * @param text - The full message text
 * @returns Array of parsed citation data with file_ids
 */
export function parseCitationList(text: string): CitationData[] {
	const citations: CitationData[] = [];

	// Find the References section
	const refSectionMatch = text.match(/### References\s*\n([\s\S]*?)$/);
	if (!refSectionMatch) return citations;

	const refText = refSectionMatch[1];
	// Match entries like "- filename.md" or "- [filename.md](url)"
	const entryRegex = /^-\s+(?:\[([^\]]+)\]\([^\)]+\)|(.+))$/gm;

	let match: RegExpExecArray | null;
	// biome-ignore lint/suspicious/noAssignInExpressions: needed for regex parsing
	while ((match = entryRegex.exec(refText)) !== null) {
		const fileName = (match[1] || match[2]).trim();
		if (fileName) {
			citations.push({
				fileName,
				title: '',
				content: '',
				paths: [],
			});
		}
	}

	return citations;
}

/**
 * Extract file_id mapping from the chunks JSON in the context.
 *
 * This parses the Document Chunks JSON to build a mapping
 * from file_name to file_id.
 *
 * @param text - The system prompt or context containing chunks JSON
 * @returns Map of file_name to file_id
 */
export function extractFileIdMapping(text: string): Map<string, string> {
	const mapping = new Map<string, string>();

	// Try to find chunks JSON in the text
	const jsonMatch = text.match(/```json\s*\n([\s\S]*?)\n```/);
	if (!jsonMatch) return mapping;

	try {
		const chunks = JSON.parse(jsonMatch[1]);
		if (Array.isArray(chunks)) {
			for (const chunk of chunks) {
				if (chunk.file_name && chunk.file_id) {
					mapping.set(chunk.file_name, chunk.file_id);
				}
			}
		}
	} catch {
		// Ignore parse errors
	}

	return mapping;
}
