<script lang="ts">
    import { authStore } from '$lib/stores/authStore';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { browser } from '$app/environment'; // Import browser environment variable

    // Function to handle logout
    async function handleLogout() {
        const FLASK_API_BASE_URL = 'http://localhost:5000'; // Keep for this specific direct logout call

        try {
            const response = await fetch(`${FLASK_API_BASE_URL}/api/logout`, {
                method: 'POST',
                credentials: 'include' // Crucial: Include session cookies
            });

            if (response.ok) {
                console.log('Logged out successfully.');
                authStore.logout(); // Clear Svelte store state
                if (browser) { // Ensure goto is only called in the browser
                    await goto('/login'); // Use await to ensure redirection happens before other actions
                }
            } else {
                const errorData = await response.json();
                console.error('Logout failed:', errorData.error || response.statusText);
                alert('Logout failed. Please try again.');
            }
        } catch (e) {
            console.error('Network error during logout:', e);
            alert('An unexpected error occurred during logout.');
        }
    }

    // Reactive statement for redirection logic
    $: {
        // This entire block runs reactivity, so ensure browser-specific APIs are guarded
        if (browser) {
            if (!$authStore.isAuthenticated && $page.url.pathname !== '/login' && $page.url.pathname !== '/register') {
                goto('/login');
            } else if ($authStore.isAuthenticated && ($page.url.pathname === '/login' || $page.url.pathname === '/register')) {
                goto('/reports');
            }
        }
    }
</script>

<svelte:head>
    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            color: #333;
        }

        .main-navbar {
            background-color: #333;
            color: white;
            padding: 0.8rem 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }

        .navbar-brand {
            font-size: 1.4rem;
            font-weight: bold;
            color: white;
            text-decoration: none;
        }

        .navbar-links {
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }

        .navbar-link {
            color: white;
            text-decoration: none;
            font-size: 1rem;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            transition: background-color 0.2s ease;
        }

        .navbar-link:hover {
            background-color: #555;
        }

        .user-info {
            font-size: 0.9rem;
            color: #ccc;
            margin-right: 1rem;
        }

        .logout-button {
            background-color: #dc3545;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: background-color 0.2s ease;
        }

        .logout-button:hover {
            background-color: #c82333;
        }

        main {
            padding: 1rem;
        }

        button {
            padding: 0.75rem 1.25rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1rem;
            transition: background-color 0.2s ease;
            white-space: nowrap;
        }
    </style>
</svelte:head>

<nav class="main-navbar">
    <a href="/" class="navbar-brand">TrustLog</a>
    <div class="navbar-links">
        {#if $authStore.isAuthenticated}
            <span class="user-info">Logged in as: {$authStore.username}</span>
            <a href="/log-entry" class="navbar-link">New Log</a>
            <a href="/reports" class="navbar-link">Reports</a>
            <button on:click={handleLogout} class="logout-button">Logout</button>
        {:else}
            <a href="/login" class="navbar-link">Login</a>
            <a href="/register" class="navbar-link">Register</a>
        {/if}
    </div>
</nav>

<main>
    <slot />
</main>