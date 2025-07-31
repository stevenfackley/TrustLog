<script lang="ts">
    import { quintOut } from 'svelte/easing';
    import { slide } from 'svelte/transition';
    import { goto } from '$app/navigation';
    import { onMount } from 'svelte';
    import { page } from '$app/stores';
    import { browser } from '$app/environment';
    import { authenticatedFetch } from '$lib/utils/api';

    // Form fields, initialized to empty or default values
    let logRecordId: number | null = null;
    let dateOfIncident: string = '';
    let category: string = '';
    let descriptionOfIncident: string = '';
    let impactTypes: string[] = [];
    let impactDetails: string = '';
    let supportingEvidenceSnippet: string = '';
    let exhibitReference: string = '';

    // Attachment related variables
    let selectedFiles: FileList | null = null;
    let fileUploadProgress: { file: File; progress: number; status: 'pending' | 'uploading' | 'complete' | 'failed' }[] = [];
    let uploadedAttachments: { id: number; filename: string; filepath: string; stored_filename: string; }[] = [];
    let allowedExtensions: string[] = [];

    // State for fetching/loading existing record
    let isEditMode = false;
    let fetchingRecord = true;
    let recordError: string | null = null;

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

    $: showSupportingEvidence = category === 'Unilateral Decision-Making';

    const FLASK_API_BASE_URL = 'http://localhost:5000'; // Still used for download links directly

    onMount(async () => {
        if (browser) { // Only run this block in the browser
            await fetchAllowedExtensions();

            const idParam = $page.url.searchParams.get('id');
            if (idParam) {
                logRecordId = parseInt(idParam, 10);
                isEditMode = true;
                await fetchLogRecordForEdit(logRecordId);
            } else {
                isEditMode = false;
                fetchingRecord = false; // No record to fetch for new entry
            }
        } else {
            // During SSR, set fetchingRecord to false to avoid hanging loaders
            fetchingRecord = false;
        }
    });

    async function fetchAllowedExtensions() {
        try {
            const response = await authenticatedFetch('/api/config/allowed_extensions');
            if (response.ok) {
                allowedExtensions = await response.json();
            } else {
                console.error('Failed to fetch allowed extensions:', await response.json());
                allowedExtensions = ['Error fetching types'];
            }
        } catch (e) {
            if (e.message !== 'Unauthorized') {
                console.error('Network error fetching allowed extensions:', e);
                allowedExtensions = ['Network Error'];
            } else {
                allowedExtensions = ['Login to see types'];
            }
        }
    }

    async function fetchLogRecordForEdit(id: number) {
        fetchingRecord = true;
        recordError = null;
        try {
            const response = await authenticatedFetch(`/api/log_records/${id}`);
            if (response.ok) {
                const record = await response.json();
                dateOfIncident = record.date_of_incident;
                category = record.category;
                descriptionOfIncident = record.description_of_incident;
                impactTypes = record.impact_types || [];
                impactDetails = record.impact_details;
                supportingEvidenceSnippet = record.supporting_evidence_snippet;
                exhibitReference = record.exhibit_reference;

                const attachmentsResponse = await authenticatedFetch(`/api/log_records/${id}/attachments`);
                if (attachmentsResponse.ok) {
                    uploadedAttachments = await attachmentsResponse.json();
                } else {
                    console.error('Failed to fetch existing attachments:', await attachmentsResponse.json());
                }
            } else {
                const errorData = await response.json();
                recordError = `Failed to load record: ${errorData.error || response.statusText}`;
                console.error('Error fetching record for edit:', errorData);
            }
        } catch (e: any) {
            if (e.message !== 'Unauthorized') {
                recordError = `Network error loading record: ${e.message}`;
            } else {
                recordError = 'Please log in to edit records.';
            }
            console.error('Network or unexpected error loading record:', e);
        } finally {
            fetchingRecord = false;
        }
    }

    async function saveLogRecord() {
        if (!dateOfIncident || !category || !descriptionOfIncident || impactTypes.length === 0) {
            alert('Please fill in all required fields (Date, Category, Description, Impact Types).');
            return;
        }

        // --- Prepare FormData for combined text and files ---
        const formData = new FormData();
        formData.append('date_of_incident', dateOfIncident);
        formData.append('category', category);
        formData.append('description_of_incident', descriptionOfIncident);
        // Stringify impact_types array as backend expects a JSON string
        formData.append('impact_types', JSON.stringify(impactTypes));
        formData.append('impact_details', impactDetails || '');
        formData.append('supporting_evidence_snippet', showSupportingEvidence ? (supportingEvidenceSnippet || '') : 'null');
        formData.append('exhibit_reference', exhibitReference || '');

        // Append selected files (for new attachments or in edit mode)
        if (selectedFiles) {
            for (let i = 0; i < selectedFiles.length; i++) {
                formData.append('files', selectedFiles[i]); // Key is 'files' (plural) for backend to getlist
            }
        }
        // --- End FormData preparation ---

        let method = 'POST';
        let url = `/api/log_records`;
        if (isEditMode && logRecordId) {
            method = 'PUT';
            url = `/api/log_records/${logRecordId}`;
        }

        try {
            // Send FormData. Do NOT set 'Content-Type' header; browser handles it for FormData.
            const response = await authenticatedFetch(url, {
                method: method,
                body: formData
            });

            if (response.ok) {
                const result = await response.json();
                console.log('Log record saved/updated successfully:', result);
                alert(`Log Record ${isEditMode ? 'Updated' : 'Saved'} Successfully!`);
                clearForm(); // Clear form on success
                goto('/reports'); // Redirect to reports
            } else {
                const errorData = await response.json();
                console.error(`Error ${isEditMode ? 'updating' : 'creating'} log record:`, errorData);
                // Since backend is atomic, this error means nothing was saved/updated.
                alert(`Failed to ${isEditMode ? 'update' : 'save'} log record: ${errorData.error || response.statusText}`);
            }
        } catch (error) {
            if (error.message !== 'Unauthorized') {
                console.error('Network or unexpected error:', error);
                alert('An unexpected error occurred while trying to save the log record.');
            }
            // No alert needed if it was an "Unauthorized" error as authenticatedFetch handles redirection.
        }
    }

    function handleFileSelect(event: Event) {
        const input = event.target as HTMLInputElement;
        if (input.files) {
            const filteredFiles = Array.from(input.files).filter(file => {
                const ext = file.name.split('.').pop()?.toLowerCase();
                return ext && allowedExtensions.includes(ext);
            });

            if (filteredFiles.length !== input.files.length) {
                alert('Some selected files have disallowed extensions and will not be uploaded.');
            }

            const dataTransfer = new DataTransfer();
            filteredFiles.forEach(file => dataTransfer.items.add(file));
            selectedFiles = dataTransfer.files;

            fileUploadProgress = filteredFiles.map(file => ({
                file,
                progress: 0,
                status: 'pending'
            }));
        } else {
            selectedFiles = null;
            fileUploadProgress = [];
        }
    }

    // `uploadAttachments` function is removed as its logic is now within `saveLogRecord`

    async function deleteAttachment(attachmentId: number, filename: string) {
        if (!confirm(`Are you sure you want to delete the attachment "${filename}"?`)) {
            return;
        }
        try {
            const response = await authenticatedFetch(`/api/attachments/${attachmentId}`, {
                method: 'DELETE',
            });
            if (response.ok) {
                alert(`Attachment "${filename}" deleted successfully.`);
                uploadedAttachments = uploadedAttachments.filter(att => att.id !== attachmentId);
            } else {
                const errorData = await response.json();
                alert(`Failed to delete attachment: ${errorData.error || response.statusText}`);
            }
        } catch (error) {
            if (error.message !== 'Unauthorized') {
                console.error('Error deleting attachment:', error);
                alert('An unexpected error occurred while deleting the attachment.');
            }
        }
    }

    function clearForm() {
        logRecordId = null;
        isEditMode = false;
        dateOfIncident = '';
        category = '';
        descriptionOfIncident = '';
        impactTypes = [];
        impactDetails = '';
        supportingEvidenceSnippet = '';
        exhibitReference = '';
        selectedFiles = null;
        fileUploadProgress = [];
        uploadedAttachments = [];
        const fileInput = document.getElementById('attachmentInput') as HTMLInputElement;
        if (fileInput) {
            fileInput.value = '';
        }
    }
</script>

<svelte:head>
    <title>{isEditMode ? 'Edit Log Entry' : 'New Log Entry'} - TrustLog</title>
</svelte:head>

<div class="page-container">
    <header class="header">
        <a href="/" class="back-button">← Back</a>
        <h1>{isEditMode ? 'Edit Log Entry' : 'New Log Entry'}</h1>
    </header>

    {#if fetchingRecord}
        <p class="status-message">Loading log record...</p>
    {:else if recordError}
        <p class="error-message">{recordError}</p>
    {:else}
        <form on:submit|preventDefault={saveLogRecord} class="log-form">
            <div class="form-group">
                <label for="dateOfIncident">Date of Incident</label>
                <input
                    type="date"
                    id="dateOfIncident"
                    name="dateOfIncident"
                    bind:value={dateOfIncident}
                    placeholder="YYYY-MM-DD"
                    required
                    class="mobile-optimized-input"
                />
            </div>

            <div class="form-group">
                <label for="category">Category</label>
                <select id="category" name="category" bind:value={category} required class="mobile-optimized-input">
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
                    name="descriptionOfIncident"
                    bind:value={descriptionOfIncident}
                    placeholder="Detailed description of the event..."
                    rows="5"
                    required
                    class="mobile-optimized-input"
                ></textarea>
            </div>

            <div class="form-group" role="group" aria-labelledby="impact-types-legend">
                <legend id="impact-types-legend" class="form-label-legend">Impact Types (Multi-select)</legend>
                <div class="checkbox-group">
                    {#each allImpactTypes as type}
                        <label class="checkbox-label">
                            <input type="checkbox" name="impactTypes" value={type} bind:group={impactTypes} />
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
                    name="impactDetails"
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
                        name="supportingEvidenceSnippet"
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
                    name="exhibitReference"
                    bind:value={exhibitReference}
                    placeholder="e.g., Exhibit 45"
                    class="mobile-optimized-input"
                />
            </div>

            {#if isEditMode && uploadedAttachments.length > 0}
                <div class="form-group existing-attachments-section">
                    <h3>Existing Attachments</h3>
                    <ul class="existing-file-list">
                        {#each uploadedAttachments as attachment (attachment.id)}
                            <li>
                                <span>{attachment.filename} ({ (attachment.filesize_bytes / 1024).toFixed(1) } KB)</span>
                                <div class="attachment-actions">
                                    <a href="{FLASK_API_BASE_URL}/api/attachments/{attachment.stored_filename}" target="_blank" download={attachment.filename} class="download-link">Download</a>
                                    <button type="button" on:click={() => deleteAttachment(attachment.id, attachment.filename)} class="delete-attachment-button">Delete</button>
                                </div>
                            </li>
                        {/each}
                    </ul>
                </div>
            {/if}

            <div class="form-group attachment-section">
                <label for="attachmentInput">Add New Attachment(s)</label>
                <input
                    type="file"
                    id="attachmentInput"
                    name="attachmentInput"
                    on:change={handleFileSelect}
                    multiple
                    class="attachment-input"
                />
                {#if allowedExtensions.length > 0}
                    <p class="allowed-extensions-info">Allowed types: .{allowedExtensions.join(', .')}</p>
                {/if}
                {#if selectedFiles && selectedFiles.length > 0}
                    <div class="file-list">
                        {#each fileUploadProgress as fileProgress, i (fileProgress.file.name)}
                            <div class="file-item">
                                <span>{fileProgress.file.name}</span>
                                <span class="file-status {fileProgress.status}">{fileProgress.status.toUpperCase()}</span>
                                {#if fileProgress.status === 'uploading'}
                                    <div class="progress-bar-container">
                                        <div class="progress-bar" style="width: {fileProgress.progress}%"></div>
                                    </div>
                                {/if}
                            </div>
                        {/each}
                    </div>
                {/if}
            </div>

            <div class="button-group">
                <button type="submit" class="save-button">{isEditMode ? 'Update Log Record' : 'Save Log Record'}</button>
                <button type="button" on:click={clearForm} class="clear-button">
                    {isEditMode ? 'Cancel Edit' : 'Clear Form'}
                </button>
            </div>
        </form>
    {/if}
</div>

<style>
    /* Mobile-first base styles */
    .page-container {
        padding: 1rem;
        max-width: 600px;
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
        flex-grow: 1;
        text-align: center;
    }

    .log-form .form-group {
        margin-bottom: 1.2rem;
    }

    .log-form label {
        display: block;
        margin-bottom: 0.5rem;
        font-weight: bold;
        color: #555;
    }

    .log-form input[type="text"],
    .log-form input[type="date"],
    .log-form textarea,
    .log-form select {
        width: 100%;
        padding: 0.8rem;
        border: 1px solid #ccc;
        border-radius: 4px;
        box-sizing: border-box;
        font-size: 1rem;
    }

    .log-form textarea {
        border-radius: 4px;
        resize: vertical;
    }

    .log-form input[type="date"] {
        -webkit-appearance: none;
        -moz-appearance: none;
        appearance: none;
        background-color: #fff;
    }

    .checkbox-group {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .checkbox-label {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        cursor: pointer;
    }

    .checkbox-label input[type="checkbox"] {
        width: auto;
        margin-right: 0.5rem;
    }

    .error-message {
        color: red;
        font-size: 0.875rem;
        margin-top: 0.5rem;
    }

    .button-group {
        display: flex;
        flex-direction: column;
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
        background-color: #28a745;
        color: white;
    }

    .save-button:hover {
        background-color: #218838;
    }

    .clear-button {
        background-color: #6c757d;
        color: white;
    }

    .clear-button:hover {
        background-color: #5a6268;
    }

    .form-label-legend {
        display: block;
        margin-bottom: 0.5rem;
        font-weight: bold;
        color: #555;
    }

    /* Styles for attachment sections */
    .attachment-section {
        margin-top: 2rem;
        padding-top: 1.5rem;
        border-top: 1px dashed #ddd;
    }

    .existing-attachments-section {
        margin-top: 1.5rem;
        padding-top: 1rem;
        border-top: 1px solid #eee;
    }

    .existing-attachments-section h3 {
        font-size: 1.1rem;
        margin-top: 0;
        margin-bottom: 0.8rem;
        color: #333;
    }

    .existing-file-list {
        list-style-type: none;
        padding: 0;
        margin: 0;
        border: 1px solid #eee;
        border-radius: 4px;
        background-color: #fcfcfc;
    }

    .existing-file-list li {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.6rem 1rem;
        border-bottom: 1px solid #f0f0f0;
        font-size: 0.9rem;
    }

    .existing-file-list li:last-child {
        border-bottom: none;
    }

    .attachment-actions {
        display: flex;
        gap: 0.5rem;
        align-items: center;
    }

    .download-link {
        color: #007bff;
        text-decoration: none;
        font-size: 0.85rem;
    }
    .download-link:hover {
        text-decoration: underline;
    }

    .delete-attachment-button {
        background-color: #dc3545;
        color: white;
        border: none;
        padding: 0.4rem 0.8rem;
        border-radius: 3px;
        cursor: pointer;
        font-size: 0.8rem;
        transition: background-color 0.2s ease;
    }
    .delete-attachment-button:hover {
        background-color: #c82333;
    }

    .attachment-input {
        padding: 0.5rem 0;
    }

    .allowed-extensions-info {
        font-size: 0.85rem;
        color: #666;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .file-list {
        margin-top: 1rem;
        border: 1px solid #eee;
        border-radius: 4px;
        padding: 0.8rem;
        background-color: #fcfcfc;
    }

    .file-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0;
        border-bottom: 1px solid #f0f0f0;
        font-size: 0.9rem;
        flex-wrap: wrap;
    }

    .file-item:last-child {
        border-bottom: none;
    }

    .file-status {
        font-weight: bold;
        padding: 0.2rem 0.5rem;
        border-radius: 3px;
        font-size: 0.75rem;
        margin-left: 0.5rem;
    }

    .file-status.pending { background-color: #ffc107; color: #333; }
    .file-status.uploading { background-color: #17a2b8; color: white; }
    .file-status.complete { background-color: #28a745; color: white; }
    .file-status.failed { background-color: #dc3545; color: white; }

    .progress-bar-container {
        width: 100%;
        background-color: #e9ecef;
        border-radius: 5px;
        height: 5px;
        margin-top: 0.5rem;
    }

    .progress-bar {
        height: 100%;
        background-color: #007bff;
        border-radius: 5px;
        transition: width 0.3s ease-in-out;
    }

    /* Media queries for larger screens */
    @media (min-width: 768px) {
        .header {
            justify-content: flex-start;
        }

        h1 {
            text-align: left;
            margin-left: 1rem;
        }

        .button-group {
            flex-direction: row;
            justify-content: flex-end;
        }

        .file-item {
            flex-wrap: nowrap;
        }
        .file-status {
            margin-left: auto;
        }
        .progress-bar-container {
            width: 30%;
            margin-top: 0;
            margin-left: 1rem;
        }
    }
</style>