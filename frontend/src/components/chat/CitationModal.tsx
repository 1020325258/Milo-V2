import { FileText, Loader2, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export interface CitationData {
	fileName: string;
	fileId?: string;
	title: string;
	content: string;
	paths: string[];
}

interface CitationModalProps {
	citation: CitationData | null;
	onClose: () => void;
}

/**
 * Modal component for displaying knowledge citation details.
 *
 * Shows the source file name, title, full content, and logical paths
 * of a knowledge chunk referenced in the LLM's response.
 *
 * When opened, fetches the full file content from the backend API.
 */
export function CitationModal({ citation, onClose }: CitationModalProps) {
	const [loading, setLoading] = useState(false);
	const [fileContent, setFileContent] = useState<string | null>(null);
	const [error, setError] = useState<string | null>(null);

	const handleKeyDown = useCallback(
		(e: KeyboardEvent) => {
			if (e.key === 'Escape') {
				onClose();
			}
		},
		[onClose],
	);

	useEffect(() => {
		if (citation) {
			document.addEventListener('keydown', handleKeyDown);
			return () => document.removeEventListener('keydown', handleKeyDown);
		}
	}, [citation, handleKeyDown]);

	// Fetch file content when citation changes
	useEffect(() => {
		if (!citation) {
			setFileContent(null);
			setError(null);
			return;
		}

		// If content is already provided, use it
		if (citation.content) {
			setFileContent(citation.content);
			return;
		}

		// Otherwise, fetch from API
		const fetchContent = async () => {
			setLoading(true);
			setError(null);

			try {
				const response = await fetch('/api/rag/file-content', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						file_id: citation.fileId || '',
						query: citation.fileName,
					}),
				});

				if (!response.ok) {
					throw new Error('Failed to fetch file content');
				}

				const data = await response.json();
				setFileContent(data.content);
			} catch (err) {
				setError(err instanceof Error ? err.message : 'Unknown error');
			} finally {
				setLoading(false);
			}
		};

		fetchContent();
	}, [citation]);

	if (!citation) return null;

	return (
		<div
			className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
			onClick={onClose}
			onKeyDown={(e) => {
				if (e.key === 'Enter') onClose();
			}}
			role="dialog"
			aria-modal="true"
			aria-label="引用详情"
		>
			<div
				className="relative w-full max-w-3xl max-h-[85vh] bg-background rounded-lg shadow-lg overflow-hidden"
				onClick={(e) => e.stopPropagation()}
				onKeyDown={(e) => e.stopPropagation()}
			>
				{/* Header */}
				<div className="flex items-center justify-between p-4 border-b">
					<div className="flex items-center gap-2">
						<FileText className="size-5 text-muted-foreground" />
						<h2 className="text-lg font-semibold">引用详情</h2>
					</div>
					<Button variant="ghost" size="icon" onClick={onClose}>
						<X className="size-4" />
					</Button>
				</div>

				{/* Content */}
				<div className="p-4 overflow-y-auto max-h-[calc(85vh-120px)]">
					{/* File info */}
					<div className="flex flex-wrap items-center gap-2 mb-4">
						<Badge variant="secondary">{citation.fileName}</Badge>
						{citation.fileId && (
							<Badge variant="outline" className="text-xs font-mono">
								{citation.fileId}
							</Badge>
						)}
					</div>

					{/* Paths */}
					{citation.paths.length > 0 && (
						<div className="mb-4">
							<h3 className="text-sm font-medium text-muted-foreground mb-1">
								逻辑路径
							</h3>
							<div className="flex flex-wrap gap-1">
								{citation.paths.map((path) => (
									<Badge key={path} variant="outline" className="text-xs">
										{path}
									</Badge>
								))}
							</div>
						</div>
					)}

					{/* Content */}
					<div>
						<h3 className="text-sm font-medium text-muted-foreground mb-2">
							文件内容
						</h3>
						<div className="p-4 bg-muted rounded-md">
							{loading && (
								<div className="flex items-center gap-2 text-muted-foreground">
									<Loader2 className="size-4 animate-spin" />
									<span>加载中...</span>
								</div>
							)}
							{error && (
								<div className="text-destructive">
									加载失败: {error}
								</div>
							)}
							{fileContent && (
								<pre className="whitespace-pre-wrap text-sm font-mono">
									{fileContent}
								</pre>
							)}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
