import { FileText, X } from 'lucide-react';
import { useCallback, useEffect } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export interface CitationData {
	fileName: string;
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
 */
export function CitationModal({ citation, onClose }: CitationModalProps) {
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
				className="relative w-full max-w-2xl max-h-[80vh] bg-background rounded-lg shadow-lg overflow-hidden"
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
				<div className="p-4 overflow-y-auto max-h-[calc(80vh-120px)]">
					{/* File info */}
					<div className="flex flex-wrap items-center gap-2 mb-4">
						<Badge variant="secondary">{citation.fileName}</Badge>
						{citation.title && citation.title !== citation.fileName && (
							<Badge variant="outline">{citation.title}</Badge>
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
							知识内容
						</h3>
						<div className="p-3 bg-muted rounded-md whitespace-pre-wrap text-sm">
							{citation.content}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
