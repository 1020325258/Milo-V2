import path from 'path';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import svgr from 'vite-plugin-svgr';

export default defineConfig({
	plugins: [react(), tailwindcss(), svgr()],
	server: {
		port: 5175,
		proxy: {
			'/api': 'http://localhost:8001',
			'/agent': 'http://localhost:8001',
			'/sessions': 'http://localhost:8001',
			'/chat': {
				target: 'http://localhost:8001',
				bypass(req) {
					// Only proxy POST /chat/ API calls to the backend.
					// GET requests are SPA page loads — serve index.html
					// so React Router can handle them.
					if (req.method !== 'POST') return '/index.html';
				},
			},
			'/model': 'http://localhost:8001',
			'/workspace': 'http://localhost:8001',
			'/schedule': 'http://localhost:8001',
			'/rag': 'http://localhost:8001',
			'/credential': 'http://localhost:8001',
		},
	},
	resolve: {
		alias: {
			'@': path.resolve(__dirname, './src'),
			'next/navigation': path.resolve(__dirname, './src/lib/next-navigation-shim.ts'),
		},
	},
	optimizeDeps: {
		include: ['mime-types'],
	},
});
