<script lang="ts">
    import { quintOut } from 'svelte/easing';
    import { slide } from 'svelte/transition';

    // Form fields, initialized to empty or default values
    let dateOfIncident: string = '';
    let category: string = '';
    let descriptionOfIncident: string = '';
    let impactTypes: string[] = []; // Array to store multiple selections
    let impactDetails: string = '';
    let supportingEvidenceSnippet: string = ''; // Conditional field
    let exhibitReference: string = '';

    // Options for Category dropdown
    const categories = [
        'Communication Breakdown',
        'Unilateral Decision-Making',
        'Gatekeeping/Parental Alienation',
        'Emotional Manipulation',
        'Obstruction/Refusal',
        'Alcohol Use'
    ];

    // Options for Impact Types multi-select
    const allImpactTypes = [
        'Impact on Co-Parenting',
        'Impact on Father-Child Relationship',
        'Emotional/Psychological Impact on Child',
        'Financial Impact',
        'Legal/Contempt Relevance',
        'Safety/Well-being Concern'
    ];

    // Reactive declaration: determines if supporting evidence snippet should be shown
    $: showSupportingEvidence = category === 'Unilateral Decision-Making';

    // Function to handle form submission
    async function saveLogRecord() {
        // Basic client-side validation (more robust server-side validation is crucial) [cite: 30, 32]
        if (!dateOfIncident || !category || !descriptionOfIncident || impactTypes.length === 0) {
            alert('Please fill in all required fields (Date, Category, Description, Impact Types).');
            return;
        }

        const logData = {
            date_of_incident: dateOfIncident,
            category: category,
            description_of_incident: descriptionOfIncident,
            impact_types: impactTypes, // Will be stringified to JSON on backend
            impact_details: impactDetails,
            supporting_evidence_snippet: showSupportingEvidence ? supportingEvidenceSnippet : null,
            exhibit_reference: exhibitReference
            // time_of_incident and created_at will be handled by the backend
        };

        console.log('Log Data to send:', logData);

        // Here you would typically send this data to your Flask backend.
        // For now, we'll just log it.
        alert('Log Record Saved (simulated)! Check console for data.');

        // Clear form after simulated submission
        clearForm();
    }

    // Function to clear the form
    function clearForm() {
        dateOfIncident = '';
        category = '';
        descriptionOfIncident = '';
        impactTypes = [];
        impactDetails = '';
        supportingEvidenceSnippet = '';
        exhibitReference = '';
    }
</script>

<svelte:head>
    <title>New Log Entry - TrustLog</title>
</svelte:head>

<div class="page-container">
    <header class="header">
        <a href="/" class="back-button">← Back</a>
        <h1>New Log Entry</h1>
    </header>

    <form on:submit|preventDefault={saveLogRecord} class="log-form">
        <div class="form-group">
            <label for="dateOfIncident">Date of Incident</label>
            <input
                type="date"
                id="dateOfIncident"
                bind:value={dateOfIncident}
                placeholder="YYYY-MM-DD"
                required
                class="mobile-optimized-input"
            />
        </div>

        <div class="form-group">
            <label for="category">Category</label>
            <select id="category" bind:value={category} required class="mobile-optimized-input">
                <option value="" disabled selected>Select a category</option>
                {#each categories as cat}
                    <option value={cat}>{cat}</option>
                {/each}
            </select>
        </div>

        <div class="form-group">
            <label for="descriptionOfIncident">Description of Incident</label>
            <textarea
                id="descriptionOfIncident"
                bind:value={descriptionOfIncident}
                placeholder="Detailed description of the event..."
                rows="5"
                required
                class="mobile-optimized-input"
            ></textarea>
        </div>

        <div class="form-group">
            <label>Impact Types (Multi-select)</label>
            <div class="checkbox-group">
                {#each allImpactTypes as type}
                    <label class="checkbox-label">
                        <input type="checkbox" value={type} bind:group={impactTypes} />
                        {type}
                    </label>
                {/each}
            </div>
            {#if impactTypes.length === 0}
                <p class="error-message">Please select at least one impact type.</p>
            {/if}
        </div>

        <div class="form-group">
            <label for="impactDetails">Impact Details</label>
            <textarea
                id="impactDetails"
                bind:value={impactDetails}
                placeholder="Additional context on the impact..."
                rows="3"
                class="mobile-optimized-input"
            ></textarea>
        </div>

        {#if showSupportingEvidence}
            <div class="form-group" transition:slide={{ duration: 300, easing: quintOut }}>
                <label for="supportingEvidenceSnippet">Supporting Evidence Snippet</label>
                <textarea
                    id="supportingEvidenceSnippet"
                    bind:value={supportingEvidenceSnippet}
                    placeholder="Direct quotes or specific textual evidence..."
                    rows="3"
                    class="mobile-optimized-input"
                ></textarea>
            </div>
        {/if}

        <div class="form-group">
            <label for="exhibitReference">Exhibit Reference</label>
            <input
                type="text"
                id="exhibitReference"
                bind:value={exhibitReference}
                placeholder="e.g., Exhibit 45"
                class="mobile-optimized-input"
            />
        </div>

        <div class="button-group">
            <button type="submit" class="save-button">Save Log Record</button>
            <button type="button" on:click={clearForm} class="clear-button">Clear Form</button>
        </div>
    </form>
</div>

<style>
    /* Mobile-first base styles */
    .page-container {
        padding: 1rem;
        max-width: 600px; /* Constrain max width for larger screens */
        margin: 0 auto;
        font-family: Arial, sans-serif;
    }

    .header {
        display: flex;
        align-items: center;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid #eee;
        padding-bottom: 1rem;
    }

    .back-button {
        background: none;
        border: none;
        color: #007bff;
        font-size: 1rem;
        cursor: pointer;
        padding: 0.5rem 1rem;
        text-decoration: none;
        margin-right: 1rem;
    }

    h1 {
        font-size: 1.5rem;
        color: #333;
        flex-grow: 1; /* Allows h1 to take remaining space */
        text-align: center;
    }

    .log-form .form-group {
        margin-bottom: 1.2rem;
    }

    .log-form label {
        display: block; /* Labels above input fields [cite: 27] */
        margin-bottom: 0.5rem;
        font-weight: bold;
        color: #555;
    }

    .log-form input[type="text"],
    .log-form input[type="date"],
    .log-form textarea,
    .log-form select {
        width: 100%; /* Single-column format [cite: 26] */
        padding: 0.8rem; /* Increased field sizes for easier tapping on mobile [cite: 27] */
        border: 1px solid #ccc;
        border-radius: 4px;
        box-sizing: border-box; /* Include padding in width */
        font-size: 1rem; /* Readable font size */
    }

    .log-form input[type="date"] {
        /* Ensure date picker icon is visible */
        -webkit-appearance: none;
        -moz-appearance: none;
        appearance: none;
        background-color: #fff; /* Ensure background is white */
    }

    .log-form textarea {
        resize: vertical; /* Allow vertical resizing */
    }

    .checkbox-group {
        display: flex;
        flex-direction: column; /* Stack checkboxes vertically on mobile */
        gap: 0.5rem;
    }

    .checkbox-label {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        cursor: pointer;
    }

    .checkbox-label input[type="checkbox"] {
        width: auto; /* Don't make checkbox full width */
        margin-right: 0.5rem;
    }

    .error-message {
        color: red;
        font-size: 0.875rem;
        margin-top: 0.5rem;
    }

    .button-group {
        display: flex;
        flex-direction: column; /* Stack buttons vertically on mobile */
        gap: 1rem;
        margin-top: 2rem;
    }

    .save-button, .clear-button {
        padding: 1rem;
        font-size: 1.1rem;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.2s ease;
    }

    .save-button {
        background-color: #28a745; /* Prominent save button [cite: 26] */
        color: white;
    }

    .save-button:hover {
        background-color: #218838;
    }

    .clear-button {
        background-color: #dc3545; /* Secondary action button */
        color: white;
    }

    .clear-button:hover {
        background-color: #c82333;
    }

    /* Media queries for larger screens (e.g., tablets/desktops) */
    @media (min-width: 768px) {
        .header {
            justify-content: flex-start;
        }

        h1 {
            text-align: left;
            margin-left: 1rem;
        }

        .button-group {
            flex-direction: row; /* Buttons side-by-side on larger screens */
            justify-content: flex-end; /* Align buttons to the right */
        }
    }
</style>