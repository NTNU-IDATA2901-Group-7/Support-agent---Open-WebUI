<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { toast } from 'svelte-sonner';
	import XMark from '../../icons/XMark.svelte';
	import { showSidebar } from '$lib/stores';
	import i18n from '$lib/i18n';
	import { uploadFile } from '$lib/apis/files';

	export let show = false;
	export let chatAttachments = [];
	export let messages: { role: string; content: string }[] = [];

	const dispatch = createEventDispatcher();

	let title = '';
	let description = '';
	let urgency = '';
	let affectedComponents = '';
	let allAttachments: { id: string; name: string }[] = [];
	let removedFiles = new Set<string>();
	$: if (show) {
		const existingIds = new Set(allAttachments.map((a) => a.id));
		const newChatAttachments = (chatAttachments ?? [])
			.filter((a) => a.id && !existingIds.has(a.id) && !removedFiles.has(a.id))
			.map((a) => ({ id: a.id, name: a.name }));
		allAttachments = [...allAttachments, ...newChatAttachments];
	}
	let errors: { [key: string]: string } = {};
	let isSubmitting = false;
	let isAutofilling = false;
	let previousFields: { title: string; description: string; urgency: string } | null = null;

	let issueTypes: { id: string; name: string; subtask: boolean }[] = [];
	let selectedIssueType = '';
	let loadingMeta = false;

	const PROJECT_KEY = 'TESTSUPP';

	const urgencyOptions = [
		{ value: '', label: '' },
		{ value: 'A', label: 'A' },
		{ value: 'B', label: 'B' },
		{ value: 'C', label: 'C' }
	];

	async function fetchProjectMeta() {
		loadingMeta = true;
		try {
			const res = await fetch(`/api/v1/jira/project-meta/${PROJECT_KEY}`, {
				headers: { Authorization: `Bearer ${localStorage.token}` }
			});
			if (res.ok) {
				const data = await res.json();
				issueTypes = (data.issue_types || []).filter((t: any) => !t.subtask);
				if (issueTypes.length > 0 && !selectedIssueType) {
					selectedIssueType = issueTypes[0].name;
				}
				loadingMeta = false;
			}
		} catch (e) {
			console.warn('Failed to fetch JIRA project meta:', e);
		}
	}

	$: if (show && issueTypes.length === 0 && !loadingMeta) {
		fetchProjectMeta();
	}

	function validateForm(): boolean {
		errors = {};

		if (!title.trim()) {
			errors.title = $i18n.t('Title is required');
		}
		if (!description.trim()) {
			errors.description = $i18n.t('Description is required');
		}
		if (!affectedComponents.trim()) {
			errors.affectedComponents = $i18n.t('Affected components are required');
		}

		return Object.keys(errors).length === 0;
	}

	async function handleFileUpload(event: Event) {
		const input = event.target as HTMLInputElement;
		console.log('handleFileUpload called, files:', input.files);
		if (input.files) {
			for (const file of Array.from(input.files)) {
				console.log('Processing file:', file.name, 'size:', file.size);
				if (file.size === 0) {
					toast.error($i18n.t('Cannot upload empty file: {{name}}', { name: file.name }));
					continue;
				}
				try {
					const uploaded = await uploadFile(localStorage.token, file, null, false);
					console.log('Upload result:', uploaded);
					if (uploaded?.id) {
						allAttachments = [
							...allAttachments,
							{ id: uploaded.id, name: uploaded.meta?.name || uploaded.filename }
						];
						console.log('Added to allAttachments:', allAttachments);
					} else {
						console.warn('Upload returned no id:', uploaded);
					}
				} catch (e) {
					console.error('Upload failed for file:', file.name, e);
					toast.error($i18n.t('Failed to upload file: {{name}}', { name: file.name }));
				}
			}
		}
		input.value = '';
	}

	function removeFile(index: number) {
		removedFiles.add(allAttachments[index].id);
		allAttachments = allAttachments.filter((_, i) => i !== index);
	}

	async function handleSubmit() {
		if (!validateForm()) {
			return;
		}

		isSubmitting = true;

		try {
			const chatAttachmentIds = new Set(
				(chatAttachments ?? []).filter((a) => a.id).map((a) => a.id)
			);

			console.log(
				'Creating ticket —',
				'chat attachments:',
				allAttachments.filter((a) => chatAttachmentIds.has(a.id)),
				'modal attachments:',
				allAttachments.filter((a) => !chatAttachmentIds.has(a.id)),
				'all attachments:',
				allAttachments
			);

			const response = await fetch('/api/v1/jira/create', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					project_key: PROJECT_KEY,
					summary: title,
					description: description,
					priority: urgency,
					issue_type: selectedIssueType || 'Task',
					file_ids: allAttachments.map((a) => a.id)
				})
			});

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to create ticket');
			}

			const result = await response.json();
			toast.success(`Jira ticket ${result.key} created successfully`);
			dispatch('submit', result);
			resetForm();
			show = false;
		} catch (error) {
			toast.error('Failed to create Jira ticket: ' + error.message);
		} finally {
			isSubmitting = false;
		}
	}

	function handleRevert() {
		if (!previousFields) return;
		title = previousFields.title;
		description = previousFields.description;
		urgency = previousFields.urgency;
		previousFields = null;
		console.log('Reverted fields to previous values');
	}

	async function handleAutofill() {
		console.log('Autofill triggered with', messages.length, 'messages');
		isAutofilling = true;
		try {
			const payload = messages.map((m) => ({ role: m.role, content: m.content }));
			console.log('Sending autofill payload:', payload);

			const response = await fetch('/api/v1/jira/autofill', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ messages: payload })
			});

			if (!response.ok) {
				const errorData = await response.json();
				console.error('Autofill request failed:', response.status, errorData);
				toast.error('Could not autofill ticket. Please fill in the fields manually.');
				return;
			}

			const result = await response.json();
			console.log('Autofill result:', result);

			previousFields = { title, description, urgency };
			title = result.title ?? title;
			description = result.description ?? description;
			urgency = result.urgency ?? urgency;
			affectedComponents = result.affectedComponents ?? affectedComponents;
			console.log(
				'Fields populated — title:',
				title,
				'description:',
				description,
				'urgency:',
				urgency,
				'affectedComponents:',
				affectedComponents
			);
		} catch (error) {
			console.error('Autofill error:', error);
			toast.error('Could not autofill ticket. Please fill in the fields manually.');
		} finally {
			isAutofilling = false;
		}
	}

	function handleCancel() {
		dispatch('cancel');
	}

	function resetForm() {
		title = '';
		description = '';
		urgency = '';
		affectedComponents = '';
		allAttachments = [];
		removedFiles = new Set<string>();
		errors = {};
		selectedIssueType = issueTypes.length > 0 ? issueTypes[0].name : '';
		previousFields = null;
	}
</script>

{#if show}
	<div
		id="jira-ticket-modal"
		class="fixed inset-0 z-40 flex items-center justify-center backdrop-blur-sm p-4 transition-all duration-200"
		style={$showSidebar ? 'left: var(--sidebar-width);' : ''}
	>
		<div
			class="w-full max-w-2xl rounded-xl bg-white dark:bg-gray-900 shadow-xl border border-gray-300 dark:border-gray-800 overflow-hidden"
		>
			<!-- Header -->
			<div
				class="flex items-center justify-between border-b border-gray-200 dark:border-gray-800 p-6"
			>
				<h2
					id="jira-ticket-modal-title"
					class="text-xl font-semibold text-gray-900 dark:text-white"
				>
					Create JIRA Ticket
				</h2>
				<button
					on:click={handleCancel}
					class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
				>
					<XMark className="size-5" />
				</button>
			</div>

			<!-- Form -->
			<form on:submit|preventDefault={handleSubmit} class="p-6 space-y-5">
				<!-- Title -->
				<div>
					<label
						for="title"
						class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
					>
						{$i18n.t('Title')} <span class="text-red-500">*</span>
					</label>
					<input
						id="title"
						type="text"
						bind:value={title}
						placeholder={$i18n.t('Describe the issue briefly')}
						class="w-full px-4 py-2 border border-gray-300 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-white transition-colors"
					/>
					{#if errors.title}
						<p class="mt-1 text-sm text-red-500">{errors.title}</p>
					{/if}
				</div>

				<!-- Description -->
				<div>
					<label
						for="description"
						class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
					>
						{$i18n.t('Description')} <span class="text-red-500">*</span>
					</label>
					<textarea
						id="description"
						bind:value={description}
						placeholder={$i18n.t('Provide detailed information about the issue')}
						rows="5"
						class="w-full px-4 py-2 border border-gray-300 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-white resize-none transition-colors"
					/>
					{#if errors.description}
						<p class="mt-1 text-sm text-red-500">{errors.description}</p>
					{/if}
				</div>

				<!-- Urgency -->
				<div>
					<label
						for="urgency"
						class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
					>
						{$i18n.t('Urgency')} <span class="text-red-500">*</span>
					</label>
					<select
						id="urgency"
						bind:value={urgency}
						class="w-full px-4 py-2 border border-gray-300 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-white transition-colors"
					>
						{#each urgencyOptions as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</div>

				<!-- Issue Type -->
				<!--<div>
					<label for="issueType" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
						{$i18n.t('Issue Type')} <span class="text-red-500">*</span>
					</label>
					{#if loadingMeta}
						<p class="text-sm text-gray-500">{$i18n.t('Loading issue types...')}</p>
					{:else if issueTypes.length > 0}
						<select
							id="issueType"
							bind:value={selectedIssueType}
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-white transition-colors"
						>
							{#each issueTypes as it}
								<option value={it.name}>{it.name}</option>
							{/each}
						</select>
					{:else}
						<input
							id="issueType"
							type="text"
							bind:value={selectedIssueType}
							placeholder="Task"
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-white transition-colors"
						/>
					{/if}
				</div> -->

				<!-- Affected Components -->
				<div>
					<label
						for="components"
						class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
					>
						{$i18n.t('Affected Components')} <span class="text-red-500">*</span>
					</label>
					<input
						id="components"
						type="text"
						bind:value={affectedComponents}
						placeholder={$i18n.t('e.g., Backend, Frontend, Database (comma-separated)')}
						class="w-full px-4 py-2 border border-gray-300 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-white transition-colors"
					/>
					{#if errors.affectedComponents}
						<p class="mt-1 text-sm text-red-500">{errors.affectedComponents}</p>
					{/if}
				</div>

				<!-- Attachments -->
				<div>
					<label
						for="attachments"
						class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
					>
						{$i18n.t('Attachments')}
					</label>
					<div class="flex items-center gap-2 mb-3">
						<label
							class="flex-1 flex items-center justify-center px-4 py-2 border-2 border-dashed border-gray-300 dark:border-gray-800 rounded-lg bg-gray-50 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer transition-colors"
						>
							<span class="text-sm font-medium text-gray-700 dark:text-gray-300"
								>{$i18n.t('Choose files')}</span
							>
							<input
								id="attachments"
								type="file"
								multiple
								on:change={handleFileUpload}
								class="hidden"
							/>
						</label>
					</div>

					<!-- Attached Files List -->
					{#if allAttachments.length > 0}
						<div class="space-y-2">
							{#each allAttachments as file, index}
								<div
									class="flex items-center justify-between px-3 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg"
								>
									<span class="text-sm text-gray-700 dark:text-gray-300">{file.name}</span>
									<button
										type="button"
										on:click={() => removeFile(index)}
										class="text-red-500 hover:text-red-700 dark:hover:text-red-400 transition-colors"
									>
										<XMark className="size-4" />
									</button>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			</form>

			<!-- Footer -->
			<div
				class="flex items-center justify-between border-t border-gray-200 dark:border-gray-800 p-6"
			>
				<div class="flex items-center gap-3">
					<button
						type="button"
						id="jira-ticket-autofill-button"
						on:click={handleAutofill}
						disabled={isAutofilling || messages.length === 0}
						class="px-4 py-2 rounded-lg bg-white text-black hover:bg-gray-100 transition-colors font-medium disabled:opacity-50"
					>
						{isAutofilling ? $i18n.t('Filling...') : $i18n.t('Autofill with AI')}
					</button>
					{#if previousFields}
						<button
							type="button"
							on:click={handleRevert}
							class="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors font-medium"
						>
							{$i18n.t('Revert')}
						</button>
					{/if}
					<button
						type="button"
						on:click={resetForm}
						class="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors font-medium"
					>
						{$i18n.t('Reset Form')}
					</button>
				</div>
				<div class="flex items-center gap-3">
					<button
						type="button"
						on:click={handleCancel}
						disabled={isSubmitting}
						class="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors font-medium disabled:opacity-50"
					>
						{$i18n.t('Cancel')}
					</button>
					<button
						type="button"
						id="jira-ticket-submit-button"
						on:click={handleSubmit}
						disabled={isSubmitting}
						class="px-4 py-2 rounded-lg bg-white text-black hover:bg-gray-100 transition-colors font-medium disabled:opacity-50"
					>
						{isSubmitting ? $i18n.t('Creating...') : $i18n.t('Create Ticket')}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
