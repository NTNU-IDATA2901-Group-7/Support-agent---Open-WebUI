<script>
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	const i18n = getContext('i18n');

	let isSyncing = false;
	let isSynced = false;
	let isLoading = true;

	async function checkSyncStatus() {
		try {
			const response = await fetch(`/api/v1/jira/status`, {
				method: 'GET',
				headers: { 'Content-Type': 'application/json' }
			});

			if (response.ok) {
				const data = await response.json();
				isSynced = data.synced;
			}
		} catch (error) {
			console.error('Error checking sync status:', error);
		} finally {
			isLoading = false;
		}
	}

	async function syncJiraTickets() {
		isSyncing = true;
		try {
			const response = await fetch(`/api/v1/jira/sync`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' }
			});

			if (!response.ok) {
				throw new Error('Failed to sync');
			}

			toast.success('Jira tickets synced successfully');
			isSynced = true;
		} catch (error) {
			toast.error('Failed to sync Jira tickets: ' + error.message);
		} finally {
			isSyncing = false;
		}
	}

	import { onMount } from 'svelte';
	onMount(() => {
		checkSyncStatus();
	});
</script>

<div class="flex flex-col gap-4">
	<div>
		<h2 class="text-lg font-semibold mb-2 dark:text-gray-100">Jira Sync</h2>
		<p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
			Sync Jira tickets to the vector database for retrieval
		</p>
	</div>

	<div class="border rounded-lg p-4 dark:border-gray-700 dark:bg-gray-800">
		<div class="flex items-center justify-between mb-4">
			<span class="text-sm dark:text-gray-300"
				>Status: {isSynced ? '✓ Synced' : '✗ Not synced'}</span
			>
		</div>

		<button
			on:click={syncJiraTickets}
			disabled={isSyncing}
			class="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-500 text-gray-100 rounded"
		>
			{isSyncing ? 'Syncing...' : 'Sync Jira Tickets'}
		</button>
	</div>
</div>
