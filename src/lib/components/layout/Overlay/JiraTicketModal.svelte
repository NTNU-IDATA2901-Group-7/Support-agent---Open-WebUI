<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { toast } from 'svelte-sonner';
	import XMark from '../../icons/XMark.svelte';
	import { showSidebar } from '$lib/stores';
	import i18n from '$lib/i18n';

	export let show = false;
	export let files = [];

	const dispatch = createEventDispatcher();

	let title = '';
	let description = '';
	let urgency = 'medium';
	let affectedComponents = '';
	let attachedFiles: File[] = [];
	let errors: { [key: string]: string } = {};
	let isSubmitting = false;

	const urgencyOptions = [
		{ value: 'A', label: 'A' },
		{ value: 'B', label: 'B' },
		{ value: 'C', label: 'C' } 
	];

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

	function handleFileUpload(event: Event) {
		const input = event.target as HTMLInputElement;
		if (input.files) {
			attachedFiles = [...attachedFiles, ...Array.from(input.files)];
		}
		input.value = '';
	}

	function removeFile(index: number) {
		attachedFiles = attachedFiles.filter((_, i) => i !== index);
	}

    async function handleSubmit() {
        if (!validateForm()) {
            return;
        }

        isSubmitting = true;

        try {
            const response = await fetch('/api/v1/jira/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_key: 'TESTSUPP', // TODO: make this configurable
                    summary: title,
                    description: description,
                    priority: urgency,
                    issue_type: 'Task'
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

	function handleCancel() {
		resetForm();
		dispatch('cancel');
	}

	function resetForm() {
		title = '';
		description = '';
		urgency = 'medium';
		affectedComponents = '';
		attachedFiles = [];
		errors = {};
	}
</script>

{#if show}
	<div
		class="fixed inset-0 z-40 flex items-center justify-center backdrop-blur-sm p-4 transition-all duration-200"
		style={$showSidebar ? 'left: var(--sidebar-width);' : ''}
	>


		<div class="w-full max-w-2xl rounded-xl bg-white dark:bg-gray-900 shadow-xl border border-gray-300 dark:border-gray-800 overflow-hidden">
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-gray-200 dark:border-gray-800 p-6">
				<h2 class="text-xl font-semibold text-gray-900 dark:text-white">{$i18n.t('Create JIRA Ticket')}</h2>
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
					<label for="title" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
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
					<label for="description" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
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
					<label for="urgency" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
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

				<!-- Affected Components -->
				<div>
					<label for="components" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
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
					<label for="attachments" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
						{$i18n.t('Attachments')}
					</label>
					<div class="flex items-center gap-2 mb-3">
						<label
							class="flex-1 flex items-center justify-center px-4 py-2 border-2 border-dashed border-gray-300 dark:border-gray-800 rounded-lg bg-gray-50 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer transition-colors"
						>
							<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$i18n.t('Choose files')}</span>
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
					{#if attachedFiles.length > 0}
						<div class="space-y-2">
							{#each attachedFiles as file, index}
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
            <div class="flex items-center justify-end gap-3 border-t border-gray-200 dark:border-gray-800 p-6">
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
                    on:click={handleSubmit}
                    disabled={isSubmitting}
                    class="px-4 py-2 rounded-lg bg-white text-black hover:bg-gray-100 transition-colors font-medium disabled:opacity-50"
                >
                    {isSubmitting ? $i18n.t('Creating...') : $i18n.t('Create Ticket')}
                </button>
            </div>
		</div>
	</div>
{/if}

