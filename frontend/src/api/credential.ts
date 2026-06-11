import { client } from './client';

export interface DefaultModelResponse {
	type: string;
	credential_id: string;
	model: string;
}

export interface SystemCredentialItem {
	id: string;
	name: string;
	data: Record<string, unknown>;
}

export interface SystemCredentialListResponse {
	credentials: SystemCredentialItem[];
	total: number;
}

export const credentialApi = {
	/** List system credentials (read-only, API keys masked). */
	listSystem: () => client.get<SystemCredentialListResponse>('/api/credentials/system'),

	/** Get the default model config from backend .env. */
 getDefaultModel: () => client.get<DefaultModelResponse>('/api/credentials/default-model'),
};
