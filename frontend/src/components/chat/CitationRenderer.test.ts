import { describe, it, expect } from 'vitest';

import { parseCitations, parseCitationList } from './CitationRenderer';

describe('parseCitations', () => {
	it('should parse single citation', () => {
		const text = '根据知识库内容，退款流程如下：[来源：退款政策.docx]';
		const result = parseCitations(text);

		expect(result.citations).toHaveLength(1);
		expect(result.citations[0].fileName).toBe('退款政策.docx');
	});

	it('should parse multiple citations', () => {
		const text = '根据文档[来源：doc1.md]和[来源：doc2.pdf]的内容...';
		const result = parseCitations(text);

		expect(result.citations).toHaveLength(2);
		expect(result.citations[0].fileName).toBe('doc1.md');
		expect(result.citations[1].fileName).toBe('doc2.pdf');
	});

	it('should return empty citations for text without citations', () => {
		const text = '这是一段普通文本，没有引用。';
		const result = parseCitations(text);

		expect(result.citations).toHaveLength(0);
	});

	it('should return original text as cleanText', () => {
		const text = '内容[来源：file.txt]继续';
		const result = parseCitations(text);

		expect(result.cleanText).toBe(text);
	});
});

describe('parseCitationList', () => {
	it('should parse citation list with titles', () => {
		const text = `这是回答内容。

---
**引用来源：**
1. 退款政策.docx - 退款流程
2. 常见问题.md - 问题解答`;

		const result = parseCitationList(text);

		expect(result).toHaveLength(2);
		expect(result[0].fileName).toBe('退款政策.docx');
		expect(result[0].title).toBe('退款流程');
		expect(result[1].fileName).toBe('常见问题.md');
		expect(result[1].title).toBe('问题解答');
	});

	it('should parse citation list without titles', () => {
		const text = `回答内容。

---
**引用来源：**
1. file1.txt
2. file2.txt`;

		const result = parseCitationList(text);

		expect(result).toHaveLength(2);
		expect(result[0].fileName).toBe('file1.txt');
		expect(result[0].title).toBe('');
	});

	it('should return empty array when no citation list', () => {
		const text = '这是普通回答，没有引用列表。';
		const result = parseCitationList(text);

		expect(result).toHaveLength(0);
	});
});
