<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import XMark from '../../icons/XMark.svelte';

	export let show = false;
	export let files = [];

	const dispatch = createEventDispatcher();

	let title = '';
	let description = '';
	let urgency = 'medium';
	let affectedComponents = '';
	let attachedFiles: File[] = [];
	let errors: { [key: string]: string } = {};

	const urgencyOptions = [
		{ value: 'A', label: 'A' },
		{ value: 'B', label: 'B' },
		{ value: 'C', label: 'C' } 
	];

	function validateForm(): boolean {
		errors = {};

		if (!title.trim()) {
			errors.title = 'Title is required';
		}
		if (!description.trim()) {
			errors.description = 'Description is required';
		}
		if (!affectedComponents.trim()) {
			errors.affectedComponents = 'Affected components are required';
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

	function handleSubmit() {
		if (!validateForm()) {
			return;
		}

		const ticketData = {
			title,
			description,
			urgency,
			affectedComponents: affectedComponents.split(',').map((c) => c.trim()),
			attachments: attachedFiles
		};

		dispatch('submit', ticketData);
		resetForm();
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
	<div class="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-sm p-4">


		<div class="w-full max-w-2xl rounded-xl bg-white dark:bg-gray-900 shadow-xl border border-gray-300 dark:border-gray-800 overflow-hidden">
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-gray-200 dark:border-gray-800 p-6">
				<h2 class="text-xl font-semibold text-gray-900 dark:text-white">Create JIRA Ticket</h2>
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
						Title <span class="text-red-500">*</span>
					</label>
					<input
						id="title"
						type="text"
						bind:value={title}
						placeholder="Describe the issue briefly"
						class="w-full px-4 py-2 border border-gray-300 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors"
					/>
					{#if errors.title}
						<p class="mt-1 text-sm text-red-500">{errors.title}</p>
					{/if}
				</div>

				<!-- Description -->
				<div>
					<label for="description" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
						Description <span class="text-red-500">*</span>
					</label>
					<textarea
						id="description"
						bind:value={description}
						placeholder="Provide detailed information about the issue"
						rows="5"
						class="w-full px-4 py-2 border border-gray-300 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none transition-colors"
					/>
					{#if errors.description}
						<p class="mt-1 text-sm text-red-500">{errors.description}</p>
					{/if}
				</div>

				<!-- Urgency -->
				<div>
					<label for="urgency" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
						Urgency <span class="text-red-500">*</span>
					</label>
					<select
						id="urgency"
						bind:value={urgency}
						class="w-full px-4 py-2 border border-gray-300 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors"
					>
						{#each urgencyOptions as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</div>

				<!-- Affected Components -->
				<div>
					<label for="components" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
						Affected Components <span class="text-red-500">*</span>
					</label>
					<input
						id="components"
						type="text"
						bind:value={affectedComponents}
						placeholder="e.g., Backend, Frontend, Database (comma-separated)"
						class="w-full px-4 py-2 border border-gray-300 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors"
					/>
					{#if errors.affectedComponents}
						<p class="mt-1 text-sm text-red-500">{errors.affectedComponents}</p>
					{/if}
				</div>

				<!-- Attachments -->
				<div>
					<label for="attachments" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
						Attachments
					</label>
					<div class="flex items-center gap-2 mb-3">
						<label
							class="flex-1 flex items-center justify-center px-4 py-2 border-2 border-dashed border-gray-300 dark:border-gray-800 rounded-lg bg-gray-50 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer transition-colors"
						>
							<span class="text-sm font-medium text-gray-700 dark:text-gray-300">Choose files</span>
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
					class="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors font-medium"
				>
					Cancel
				</button>
				<button
					type="button"
					on:click={handleSubmit}
					class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors font-medium"
				>
					Create Ticket
				</button>
			</div>
		</div>
	</div>
{/if}
