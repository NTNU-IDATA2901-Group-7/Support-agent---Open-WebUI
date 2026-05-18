import adapter from '@sveltejs/adapter-static';
import * as child_process from 'node:child_process';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import fs from 'node:fs';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	// Consult https://kit.svelte.dev/docs/integrations#preprocessors
	// for more information about preprocessors
	preprocess: vitePreprocess(),
	kit: {
		// adapter-auto only supports some environments, see https://kit.svelte.dev/docs/adapter-auto for a list.
		// If your environment is not supported or you settled on a specific environment, switch out the adapter.
		// See https://kit.svelte.dev/docs/adapters for more information about adapters.
		adapter: adapter({
			pages: 'build',
			assets: 'build',
			fallback: 'index.html'
		}),
		// poll for new version name every 60 seconds (to trigger reload mechanic in +layout.svelte)
		version: {
			name: (() => {
				try {
					return child_process.execSync('git rev-parse HEAD').toString().trim();
				} catch {
					// if git is not available, fallback to package.json version
					// or current timestamp
					try {
						return (
							JSON.parse(fs.readFileSync(new URL('./package.json', import.meta.url), 'utf8'))
								?.version || Date.now().toString()
						);
					} catch {
						return Date.now().toString();
					}
				}
			})(),
			pollInterval: 60000
		}
	},
	vitePlugin: {
		inspect: false
	},
	onwarn(warning) {
		// Silently ignore these warnings
		const ignoreList = [
			'css-unused-selector',
			'a11y_consider_explicit_label',
			'element_invalid_self_closing_tag',
			'export_let_unused',
			'store_not_subscribe'
		];

		if (!ignoreList.includes(warning.code)) {
			console.warn(warning.message);
		}
	}
};

export default config;
