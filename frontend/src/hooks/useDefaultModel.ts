import { useState, useCallback } from 'react';

import { credentialApi } from '@/api';
import type { ChatModelConfig } from '@/api';

interface UseDefaultModelOptions {
	/** Called when the fetch fails. */
	onError?: (error: Error) => void;
}

/**
 * Fetches the default model config from backend .env.
 * Returns the model config and loading state.
 */
export function useDefaultModel(options?: UseDefaultModelOptions) {
	const [model, setModel] = useState<ChatModelConfig | null>(null);
	const [modelName, setModelName] = useState('');
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<Error | null>(null);

	const fetch = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await credentialApi.getDefaultModel();
			const config: ChatModelConfig = {
				type: res.type,
				credential_id: res.credential_id,
				model: res.model,
				parameters: {},
			};
			setModel(config);
			setModelName(res.model);
			return config;
		} catch (e) {
			const err = e as Error;
			setError(err);
			setModel(null);
			setModelName('');
			options?.onError?.(err);
			return null;
		} finally {
			setLoading(false);
		}
	}, [options]);

	return { model, modelName, loading, error, fetch };
}
