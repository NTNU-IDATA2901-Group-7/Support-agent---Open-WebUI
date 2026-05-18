<script>
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { onMount } from 'svelte';

	const i18n = getContext('i18n');

	let isSyncing = false;
	let isSynced = false;
	let isLoading = true;
	let isWiping = false;
	let lastSyncedAt = null;
	let lastWipedAt = null;

	async function checkSyncStatus() {
		try {
			const response = await fetch(`/api/v1/jira/status`, {
				method: 'GET',
				headers: { 'Content-Type': 'application/json' }
			});

			if (response.ok) {
				const data = await response.json();
				isSynced = data.synced;
				lastSyncedAt = data.last_synced_at;
				lastWipedAt = data.last_wiped_at;
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
			await checkSyncStatus();
		} catch (error) {
			toast.error('Failed to sync Jira tickets: ' + error.message);
		} finally {
			isSyncing = false;
		}
	}

	async function wipeJiraCollection() {
		isWiping = true;
		try {
			const response = await fetch(`/api/v1/jira/wipe`, {
				method: 'DELETE',
				headers: { 'Content-Type': 'application/json' }
			});

			if (!response.ok) {
				throw new Error('Failed to wipe');
			}

			toast.success('Jira collection wiped successfully');
			await checkSyncStatus();
		} catch (error) {
			toast.error('Failed to wipe Jira collection: ' + error.message);
		} finally {
			isWiping = false;
		}
	}

	onMount(() => {
		checkSyncStatus();
	});
</script>

<form class="flex flex-col h-full justify-between space-y-3 text-sm">
	<div class=" space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		<div>
			<div class=" mb-2 text-sm font-medium">{$i18n.t('Jira Knowledge Base')}</div>

			{#if !isLoading}
				<div class="flex rounded-md py-2 px-3 w-full text-gray-500 dark:text-gray-400">
					<div class="self-center mr-3">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								fill-rule="evenodd"
								d="M8 15A7 7 0 1 0 8 1a7 7 0 0 0 0 14Zm.75-10.25a.75.75 0 0 0-1.5 0v3.5a.75.75 0 0 0 .4.66l2.5 1.25a.75.75 0 1 0 .7-1.32L8.75 7.87V4.75Z"
								clip-rule="evenodd"
							/>
						</svg>
					</div>
					<div class="self-center text-sm font-medium">
						{#if isSynced && lastSyncedAt}
							Last synced: {new Date(lastSyncedAt).toLocaleString()}
						{:else if lastWipedAt && (!lastSyncedAt || lastWipedAt > lastSyncedAt)}
							<span class="text-red-500">Wiped</span>
						{:else}
							Not synced
						{/if}
					</div>
				</div>
			{/if}

			<button
				type="button"
				class="flex rounded-md py-2 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
				disabled={isSyncing}
				on:click={syncJiraTickets}
			>
				<div class="self-center mr-3">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 16 16"
						fill="currentColor"
						class="w-4 h-4"
					>
						<path
							fill-rule="evenodd"
							d="M13.836 2.477a.75.75 0 0 1 .75.75v3.182a.75.75 0 0 1-.75.75h-3.182a.75.75 0 0 1 0-1.5h1.37l-.84-.841a4.5 4.5 0 0 0-7.08.932.75.75 0 0 1-1.3-.75 6 6 0 0 1 9.44-1.242l.842.84V3.227a.75.75 0 0 1 .75-.75Zm-.911 7.5A.75.75 0 0 1 13.199 11a6 6 0 0 1-9.44 1.241l-.84-.84v1.371a.75.75 0 0 1-1.5 0V9.591a.75.75 0 0 1 .75-.75H5.35a.75.75 0 0 1 0 1.5H3.98l.841.841a4.5 4.5 0 0 0 7.08-.932.75.75 0 0 1 1.025-.273Z"
							clip-rule="evenodd"
						/>
					</svg>
				</div>
				<div class="self-center text-sm font-medium">
					{isSyncing ? $i18n.t('Syncing...') : $i18n.t('Sync Jira Tickets')}
				</div>
			</button>

			<button
				type="button"
				class="flex rounded-md py-2 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition text-red-500"
				disabled={isWiping}
				on:click={wipeJiraCollection}
			>
				<div class="self-center mr-3">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 16 16"
						fill="currentColor"
						class="w-4 h-4"
					>
						<path
							fill-rule="evenodd"
							d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.3l.815 8.15A1.5 1.5 0 0 0 5.357 15h5.285a1.5 1.5 0 0 0 1.493-1.35l.815-8.15h.3a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm2.25-.75a.75.75 0 0 0-.75.75V4h3v-.75a.75.75 0 0 0-.75-.75h-1.5ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.075l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.787l-.275 5.5a.75.75 0 0 1-1.498-.075l.275-5.5a.75.75 0 0 1 .786-.711Z"
							clip-rule="evenodd"
						/>
					</svg>
				</div>
				<div class="self-center text-sm font-medium">
					{isWiping ? $i18n.t('Wiping...') : $i18n.t('Wipe Collection')}
				</div>
			</button>
		</div>
	</div>
</form>
