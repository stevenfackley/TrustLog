// src/lib/stores/authStore.ts (Updated with forceLogout)
import { writable } from 'svelte/store';
import { browser } from '$app/environment';

interface AuthState {
    isAuthenticated: boolean;
    username: string | null;
}

// Initialize store with data from localStorage if available (for persistence across reloads)
const initialAuth: AuthState = {
    isAuthenticated: browser ? localStorage.getItem('isAuthenticated') === 'true' : false,
    username: browser ? localStorage.getItem('username') : null,
};

const auth = writable<AuthState>(initialAuth);

// Subscribe to changes and update localStorage for persistence
if (browser) {
    auth.subscribe(value => {
        localStorage.setItem('isAuthenticated', String(value.isAuthenticated));
        localStorage.setItem('username', value.username || '');
    });
}

export const authStore = {
    subscribe: auth.subscribe,
    login: (username: string) => {
        auth.update(state => ({ isAuthenticated: true, username }));
    },
    logout: () => { // This is for explicit logout initiated by user
        auth.update(state => ({ isAuthenticated: false, username: null }));
    },
    // NEW: forceLogout for handling unauthorized API responses
    forceLogout: () => {
        if (browser) {
            localStorage.removeItem('isAuthenticated');
            localStorage.removeItem('username');
            // Explicitly set the store state
            auth.set({ isAuthenticated: false, username: null });
        }
    }
};