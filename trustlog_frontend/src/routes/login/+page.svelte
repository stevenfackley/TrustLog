<script lang="ts">
    import { goto } from '$app/navigation';
    import { authStore } from '$lib/stores/authStore';
    import { authenticatedFetch } from '$lib/utils/api'; // Import authenticatedFetch

    let username = '';
    let password = '';
    let loginError: string | null = null;
    let loading = false;

    // FLASK_API_BASE_URL is now handled internally by authenticatedFetch

    async function handleLogin() {
        loginError = null;
        loading = true;

        try {
            // Use authenticatedFetch for login
            const response = await authenticatedFetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
                // credentials: 'include' is handled by authenticatedFetch
            });

            if (response.ok) {
                const result = await response.json();
                console.log('Login successful:', result.message);
                authStore.login(result.username); // Update the Svelte store
                goto('/reports'); // Redirect to reports page
            } else {
                const errorData = await response.json();
                loginError = errorData.error || 'Login failed. Please check your credentials.';
                console.error('Login error:', errorData);
            }
        } catch (e: any) {
            // authenticatedFetch re-throws errors, including if it handles a 401 redirect
            if (e.message !== 'Unauthorized') { // Avoid showing an alert if already redirected
                loginError = 'Network error or server unreachable. Please try again.';
                console.error('Network error during login:', e);
            }
        } finally {
            loading = false;
        }
    }
</script>

<svelte:head>
    <title>Login - TrustLog</title>
</svelte:head>

<div class="auth-container">
    <h1>Login to TrustLog</h1>
    <form on:submit|preventDefault={handleLogin} class="auth-form">
        <div class="form-group">
            <label for="username">Username:</label>
            <input
                type="text"
                id="username"
                name="username"
                bind:value={username}
                required
                autocomplete="username"
                class="auth-input"
                disabled={loading}
            />
        </div>
        <div class="form-group">
            <label for="password">Password:</label>
            <input
                type="password"
                id="password"
                name="password"
                bind:value={password}
                required
                autocomplete="current-password"
                class="auth-input"
                disabled={loading}
            />
        </div>

        {#if loginError}
            <p class="error-message">{loginError}</p>
        {/if}

        <button type="submit" class="auth-button" disabled={loading}>
            {#if loading}Logging in...{:else}Login{/if}
        </button>
    </form>
    <p class="auth-link-text">Don't have an account? <a href="/register">Register here</a></p>
</div>

<style>
    .auth-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        background-color: #f0f2f5;
        font-family: Arial, sans-serif;
        padding: 1rem;
        box-sizing: border-box;
    }

    h1 {
        color: #333;
        margin-bottom: 2rem;
        font-size: 2rem;
    }

    .auth-form {
        background-color: white;
        padding: 2rem;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        width: 100%;
        max-width: 380px;
        box-sizing: border-box;
    }

    .form-group {
        margin-bottom: 1.5rem;
    }

    .form-group label {
        display: block;
        margin-bottom: 0.5rem;
        font-weight: bold;
        color: #555;
    }

    .auth-input {
        width: 100%;
        padding: 0.8rem;
        border: 1px solid #ccc;
        border-radius: 4px;
        box-sizing: border-box;
        font-size: 1rem;
    }

    .auth-input:focus {
        border-color: #007bff;
        outline: none;
        box-shadow: 0 0 0 0.1rem rgba(0, 123, 255, 0.25);
    }

    .error-message {
        color: #dc3545;
        font-size: 0.875rem;
        margin-top: -1rem;
        margin-bottom: 1rem;
        text-align: center;
    }

    .auth-button {
        width: 100%;
        padding: 1rem;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 4px;
        font-size: 1.1rem;
        cursor: pointer;
        transition: background-color 0.2s ease;
    }

    .auth-button:hover:not(:disabled) {
        background-color: #0056b3;
    }

    .auth-button:disabled {
        background-color: #a0c3e0;
        cursor: not-allowed;
    }

    .auth-link-text {
        margin-top: 1.5rem;
        font-size: 0.9rem;
        color: #666;
    }

    .auth-link-text a {
        color: #007bff;
        text-decoration: none;
        font-weight: bold;
    }

    .auth-link-text a:hover {
        text-decoration: underline;
    }
</style>