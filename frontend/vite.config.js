import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
	base: '/',
	server: {
		// Does the job Caddy does in production: same-origin /api, so no CORS in dev.
		proxy: {
			'/api': process.env.API_PROXY_TARGET || 'http://localhost:8000',
		},
		// File events don't always cross Docker bind mounts (Windows/macOS).
		watch: { usePolling: process.env.VITE_USE_POLLING === 'true' },
	},
})
