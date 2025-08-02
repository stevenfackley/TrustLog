// src/lib/utils/api.ts
import { authStore } from '$lib/stores/authStore';
import { goto } from '$app/navigation';
import { browser } from '$app/environment';

const FLASK_API_BASE_URL = 'http://localhost:5000'; // Your backend URL

/**
 * A wrapper around `fetch` that automatically includes credentials (cookies)
 * and handles unauthorized responses by redirecting to login.
 * @param endpoint The API endpoint (e.g., '/api/log_records')
 * @param options Fetch options (method, headers, body, etc.)
 * @returns Promise<Response>
 */
export async function authenticatedFetch(endpoint: string, options?: RequestInit): Promise<Response> {
    const url = `${FLASK_API_BASE_URL}${endpoint}`;

    const defaultOptions: RequestInit = {
        ...options,
        credentials: 'include' // Always include cookies for authenticated requests
    };

    try {
        const response = await fetch(url, defaultOptions);

        if (response.status === 401) {
            console.warn('Authentication expired or unauthorized access. Attempting to clear session and redirect to login.');
            // This is the core fix: Immediately clear localStorage and authStore state
            // and then perform the redirect.
            authStore.forceLogout(); // Call the new forceLogout to ensure localStorage is cleared directly.
            if (browser) {
                await goto('/login');
            }
            throw new Error('Unauthorized'); // Stop further processing
        }

        return response;
    } catch (error) {
        console.error(`Network error or problem with fetch to ${url}:`, error);
        throw error; // Re-throw the error for component-specific handling
    }
}