<script lang="ts">
    // You can add any global script here if needed
</script>

<svelte:head>
    <title>TrustLog - Your Secure Tracking Companion</title>
</svelte:head>

<div class="home-container">
    <h1>Welcome to TrustLog</h1>
    <p>Securely manage and track your incidents with peace of mind.</p>

    <nav class="main-nav">
        <a href="/log-entry" class="nav-button">Add New Log Entry</a>
        <a href="/reports" class="nav-button">View Reports</a>
        </nav>
</div>

<style>
    .home-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        text-align: center;
        padding: 1rem;
        font-family: Arial, sans-serif;
    }

    h1 {
        color: #333;
        font-size: 2rem;
        margin-bottom: 1rem;
    }

    p {
        color: #666;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    .main-nav {
        display: flex;
        flex-direction: column; /* Stack buttons vertically on mobile */
        gap: 1.5rem;
        width: 100%;
        max-width: 300px;
    }

    .nav-button {
        display: block; /* Make sure links fill their container */
        padding: 1rem 1.5rem;
        background-color: #007bff;
        color: white;
        text-decoration: none;
        border-radius: 8px;
        transition: background-color 0.3s ease;
        font-size: 1.2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }

    .nav-button:hover {
        background-color: #0056b3;
    }

    @media (min-width: 600px) {
        .main-nav {
            flex-direction: row; /* Buttons side-by-side on larger screens */
            max-width: 500px;
            justify-content: center;
        }

        .nav-button {
            flex: 1; /* Distribute space evenly */
        }
    }
</style>