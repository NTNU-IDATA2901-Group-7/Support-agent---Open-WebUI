// Type definitions for application stores and models
// This file extends the base types to include optional properties accessed in the codebase

export interface Config {
	auth?: boolean;
	auth_trusted_header?: boolean;
	enable_api_keys?: boolean;
	enable_signup?: boolean;
	enable_login_form?: boolean;
	enable_web_search?: boolean;
	enable_google_drive_integration?: boolean;

	// Extended optional properties
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
	folder_max_file_count?: number;
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
	chatDirection?: 'auto' | 'ltr' | 'rtl' | 'LTR' | 'RTL' | string;
	[key: string]: any;
}

export interface Model {
	id?: string;
	name?: string;
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
