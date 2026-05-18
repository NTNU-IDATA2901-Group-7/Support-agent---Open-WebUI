<script lang="ts">
	import { getContext, tick } from 'svelte';
	import { Confetti } from 'svelte-confetti';
	import { WEBUI_NAME, settings, showSidebar } from '$lib/stores';
	import { get } from 'svelte/store';
	import Modal from './common/Modal.svelte';
	import { updateUserSettings } from '$lib/apis/users';
	import XMark from '$lib/components/icons/XMark.svelte';

	const i18n = getContext('i18n') as any;
	const isDark = document.documentElement.classList.contains('dark');

	export let show = false;
	export const FEATURES_VERSION = 'jira-1.0';

	const dismissModal = async () => {
		await settings.update((s) => ({ ...s, featuresVersion: FEATURES_VERSION }));
		await updateUserSettings(localStorage.token, { ui: $settings });
		show = false;
	};

	const openJiraTicketModal = () => {
		const jiraTicketButton = document.getElementById('jira-ticket-button');
		jiraTicketButton?.click();
	};

	const closeJiraTicketModal = () => {
		const jiraModalCloseButton = document.querySelector('#jira-ticket-modal button');
		(jiraModalCloseButton as HTMLButtonElement | null)?.click();
	};

	const isMobileViewport = () => window.matchMedia('(max-width: 767px)').matches;
	const isNarrowViewport = () => window.matchMedia('(max-width: 1100px)').matches;
	const getFinalStepAlign = () => (isNarrowViewport() ? 'start' : 'center');

	const startTour = async () => {
		await dismissModal();

		if (isMobileViewport() && get(showSidebar)) {
			showSidebar.set(false);
			await tick();
		}

		setTimeout(async () => {
			const { driver } = await import('driver.js');
			await import('driver.js/dist/driver.css');

			const driverObj = driver({
				showProgress: true,
				progressText: '{{current}} / {{total}}',
				nextBtnText: $i18n.t('Next →'),
				prevBtnText: $i18n.t('← Back'),
				doneBtnText: $i18n.t("Let's Go!"),

				popoverClass: 'owui-tour-popover',
				overlayColor: isDark ? 'rgba(0,0,0,0.65)' : 'rgba(23,23,23,0.45)',
				stagePadding: 8,
				stageRadius: 14,

				steps: [
					{
						element: '#jira-ticket-button',
						popover: {
							title: $i18n.t('Create a Jira Ticket'),
							description: $i18n.t(
								'Click this button at any point in a conversation to raise a Jira ticket. You can use AI to automatically fill the fields based on your chat.'
							),
							side: 'top',
							align: 'center',
							popoverClass: 'owui-tour-popover owui-tour-popover--jira-button',
							onNextClick: () => {
								openJiraTicketModal();
								setTimeout(() => driverObj.moveNext(), 300);
							}
						}
					},
					{
						element: '#jira-ticket-modal-title',
						popover: {
							title: $i18n.t('Fill in Ticket Details'),
							description: $i18n.t(
								'The Jira ticket form helps you add a clear title, detailed description, urgency, affected components, and optional attachments before creating the ticket.'
							),
							side: 'top',
							align: 'start',
							onNextClick: () => {
								setTimeout(() => driverObj.moveNext(), 150);
							},
							onPrevClick: () => {
								closeJiraTicketModal();
								setTimeout(() => driverObj.movePrevious(), 300);
							}
						}
					},
					{
						element: '#jira-ticket-autofill-button',
						popover: {
							title: $i18n.t('Autofill with AI'),
							description: $i18n.t(
								'Use Autofill with AI to generate a draft ticket from the current conversation, then review and adjust before submitting.'
							),
							side: 'top',
							align: 'start'
						}
					},
					{
						element: '#jira-ticket-submit-button',
						popover: {
							title: $i18n.t('Create the Ticket'),
							description: $i18n.t(
								'When everything looks good, press Create Ticket to submit it to Jira directly from the chat.'
							),
							side: 'top',
							align: 'end',
							onNextClick: () => {
								closeJiraTicketModal();
								showSidebar.set(true);
								setTimeout(() => driverObj.moveNext(), 300);
							}
						}
					},
					{
						element: '#sidebar-new-chat-button',
						popover: {
							title: $i18n.t('Start a New Conversation'),
							description: $i18n.t(
								'Use this button any time you want to begin a fresh support chat.'
							),
							side: 'bottom',
							align: getFinalStepAlign(),
							popoverClass: 'owui-tour-popover owui-tour-popover--new-chat',
							onPrevClick: () => {
								openJiraTicketModal();
								setTimeout(() => driverObj.movePrevious(), 300);
							}
						}
					}
				]
			});

			driverObj.drive();
		}, 400);
	};
</script>

<Modal bind:show size="md">
	<div class="px-6 pt-5 dark:text-white text-black">
		<div class="flex justify-between items-start">
			<div>
				<div class="text-xl font-semibold">
					{$i18n.t('Welcome to')}
					{$WEBUI_NAME}!
					<Confetti x={[-1, -0.25]} y={[0, 0.5]} />
				</div>
				<div class="text-sm text-gray-500 dark:text-gray-400 mt-1">
					{$i18n.t('Your AI-powered support assistant')}
				</div>
			</div>
			<button class="self-start mt-1" on:click={dismissModal} aria-label={$i18n.t('Close')}>
				<XMark className="size-5" />
			</button>
		</div>
	</div>

	<div class="w-full px-6 pb-2 pt-5 text-gray-700 dark:text-gray-100 space-y-3">
		<!-- RAG -->
		<div class="flex gap-3 items-start">
			<div
				class="shrink-0 flex items-center justify-center rounded-xl bg-gray-100 dark:bg-gray-700/50 size-9 mt-0.5"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					class="size-4.5 text-gray-600 dark:text-gray-300"
				>
					<path d="M12 20h9" />
					<path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
				</svg>
			</div>
			<div>
				<div class="font-semibold text-sm">{$i18n.t('AI-Powered Answers')}</div>
				<div class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
					{$i18n.t(
						"Ask ReSolwr anything - get answers to general questions and Solwr-specific issues alike, backed by Solwr's own documentation and support history."
					)}
				</div>
			</div>
		</div>

		<!-- Jira -->
		<div class="flex gap-3 items-start">
			<div
				class="shrink-0 flex items-center justify-center rounded-xl bg-gray-100 dark:bg-gray-700/50 size-9 mt-0.5"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					class="size-4.5 text-white"
				>
					<path d="M3 7h18v3a2 2 0 100 4v3H3v-3a2 2 0 100-4V7z" />
					<line x1="12" y1="7" x2="12" y2="17" />
				</svg>
			</div>
			<div>
				<div class="font-semibold text-sm">{$i18n.t('Create Jira Tickets')}</div>
				<div class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
					{$i18n.t(
						"Can't find the answer? Create a support ticket without leaving the chat - the AI fills in the details for you."
					)}
				</div>
			</div>
		</div>
	</div>

	<div class="flex items-center justify-between px-6 pb-5 pt-4">
		<button
			on:click={dismissModal}
			class="text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition"
		>
			{$i18n.t('Skip tour')}
		</button>
		<button
			on:click={startTour}
			class="px-4 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
		>
			{$i18n.t('Take the tour →')}
		</button>
	</div>
</Modal>
