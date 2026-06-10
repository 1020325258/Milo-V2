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
			'/chat': 'http://localhost:8001',
			'/credential': 'http://localhost:8001',
			'/model': 'http://localhost:8001',
			'/workspace': 'http://localhost:8001',
			'/schedule': 'http://localhost:8001',
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
