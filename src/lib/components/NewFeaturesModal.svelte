<script lang="ts">
    import { getContext } from 'svelte';
    import { Confetti } from 'svelte-confetti';
    import { WEBUI_NAME, settings, showSidebar } from '$lib/stores';
    import { get } from 'svelte/store';
    import Modal from './common/Modal.svelte';
    import { updateUserSettings } from '$lib/apis/users';
    import XMark from '$lib/components/icons/XMark.svelte';
    

    const i18n = getContext('i18n');
    const isDark = document.documentElement.classList.contains('dark');

    export let show = false;
    export const FEATURES_VERSION = 'jira-1.0';

    const dismissModal = async () => {
        await settings.update((s) => ({ ...s, featuresVersion: FEATURES_VERSION }));
        await updateUserSettings(localStorage.token, { ui: $settings });
        show = false;
    };

    const startTour = async () => {
        await dismissModal();

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
                                'Click this button at any point in a conversation to raise a Jira support ticket. The form will pre-fill using your chat context.'
                            ),
                            side: 'top',
                            align: 'center'
                        }
                    },
                    {
                      element: '#chat-input',
                      popover: {
                        title: $i18n.t('Describe Your Issue'),
                        description: $i18n.t('...'),
                        side: 'top',
                        align: 'start',
                        onNextClick: () => {
                          showSidebar.set(true); // make target exist
                          setTimeout(() => driverObj.moveNext(), 250);
                        }
                      }
                    },
                    {
                      element: '#sidebar-new-chat-button',
                      popover: {
                        title: $i18n.t('Start a New Conversation'),
                        description: $i18n.t('...'),
                        side: 'bottom',
                        align: 'start'
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
                    {$i18n.t('Welcome to')} {$WEBUI_NAME}!
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
        <!-- Jira -->
        <div class="flex gap-3 items-start">
            <div
                class="shrink-0 flex items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-900/40 size-9 mt-0.5"
            >
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    class="size-4.5 text-blue-600 dark:text-blue-300"
                >
                    <path d="M3 7h18v3a2 2 0 100 4v3H3v-3a2 2 0 100-4V7z" />
                    <line x1="12" y1="7" x2="12" y2="17" />
                </svg>
            </div>
            <div>
                <div class="font-semibold text-sm">{$i18n.t('Create Jira Tickets')}</div>
                <div class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                    {$i18n.t(
                        'Raise support tickets directly from your chat — the AI auto-fills the details.'
                    )}
                </div>
            </div>
        </div>

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
                        "Ask anything — answers are sourced from your company's documentation with citations."
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