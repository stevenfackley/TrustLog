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
            // If unauthorized, clear local auth state and redirect to login
            console.warn('Authentication expired or unauthorized access. Redirecting to login.');
            authStore.logout(); // Clear the client-side state
            if (browser) { // Ensure goto is called only in the browser
                await goto('/login');
            }
            // Throw an error to stop further processing in the calling function
            throw new Error('Unauthorized');
        }

        return response;
    } catch (error) {
        console.error(`Network error or problem with fetch to ${url}:`, error);
        // Re-throw the error so calling components can handle it (e.g., display a message)
        throw error;
    }
}