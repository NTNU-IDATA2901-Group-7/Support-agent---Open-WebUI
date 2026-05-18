// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface Platform {}
	}
}

// Extend Config type to include optional properties accessed throughout the app
// This suppresses "property does not exist" errors for optional config properties
declare module '$lib/interfaces' {
	export interface Config {
		file?: {
			max_count?: number;
			max_size?: number;
			image_compression?: {
				width?: number;
				height?: number;
			};
		};
		features?: {
			enable_code_interpreter?: boolean;
			enable_notes?: boolean;
			[key: string]: any;
		};
		[key: string]: any;
	}

	export interface Settings {
		imageCompression?: boolean;
		imageCompressionSize?: {
			width?: number;
			height?: number;
		};
		imageCompressionInChannels?: boolean;
		showFormattingToolbar?: boolean;
		insertPromptAsRichText?: boolean;
		chatDirection?: string;
		[key: string]: any;
	}

	export interface Model {
		info?: {
			meta?: {
				capabilities?: {
					vision?: boolean;
					file_upload?: boolean;
					web_search?: boolean;
					image_generation?: boolean;
					code_interpreter?: boolean;
					[key: string]: any;
				};
				[key: string]: any;
			};
			[key: string]: any;
		};
		filters?: Array<any>;
		has_user_valves?: boolean;
		[key: string]: any;
	}
}

export {};
