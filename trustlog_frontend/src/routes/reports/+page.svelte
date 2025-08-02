<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { goto } from '$app/navigation';
    import { slide } from 'svelte/transition';
    import { browser } from '$app/environment';
    import { authenticatedFetch } from '$lib/utils/api';
    import {
        Chart,
        Title,
        Tooltip,
        Legend,
        BarElement,
        CategoryScale,
        LinearScale,
        BarController,
    } from 'chart.js';

    Chart.register(
        Title,
        Tooltip,
        Legend,
        BarElement,
        CategoryScale,
        LinearScale,
        BarController
    );

    interface LogRecord {
        id: number;
        date_of_incident: string;
        time_of_incident: string | null;
        category: string;
        description_of_incident: string;
        impact_types: string[];
        impact_details: string | null;
        supporting_evidence_snippet: string | null;
        exhibit_reference: string | null;
        created_at: string;
        attachment_count: number;
    }

    interface Attachment {
        id: number;
        log_record_id: number;
        filename: string;
        stored_filename: string;
        filepath: string;
        filetype: string;
        filesize_bytes: number;
        upload_date: string;
    }

    let logRecords: LogRecord[] = [];
    let loading = true;
    let error: string | null = null;
    let activeTab: 'summary' | 'detailed' | 'charts' = 'detailed';

    // Filter states
    let filterCategory: string = '';
    let filterStartDate: string = '';
    let filterEndDate: string = '';
    let sortBy: string = 'date_of_incident';
    let sortOrder: 'desc' | 'asc' = 'desc';
    let showFilters = false;

    // Attachment viewing states
    let expandedLogId: number | null = null;
    let attachmentsForExpandedLog: Attachment[] = [];
    let fetchingAttachments = false;
    let attachmentsError: string | null = null;

    // Options for Category dropdown
    const categories = [
        'Communication Breakdown',
        'Unilateral Decision-Making',
        'Gatekeeping/Parental Alienation',
        'Emotional Manipulation',
        'Obstruction/Refusal',
        'Alcohol Use'
    ];

    const FLASK_API_BASE_URL = 'http://localhost:5000';

    let chartCanvas: HTMLCanvasElement;
    let myChart: Chart | null = null;

    function createOrUpdateChart() {
        if (!browser || !chartCanvas || activeTab !== 'charts') return;

        if (myChart) {
            myChart.destroy();
        }

        if (categoryChartDataValues.length === 0) {
            myChart = null;
            return;
        }

        myChart = new Chart(chartCanvas, {
            type: 'bar',
            data: {
                labels: categoryChartLabels,
                datasets: [
                    {
                        label: 'Number of Incidents',
                        backgroundColor: 'rgba(0, 123, 255, 0.5)',
                        borderColor: 'rgba(0, 123, 255, 1)',
                        borderWidth: 1,
                        data: categoryChartDataValues,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Incidents by Category',
                        font: {
                            size: 16
                        }
                    },
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Count'
                        },
                        ticks: {
                            precision: 0 // Ensures only whole numbers are used as ticks
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Category'
                        }
                    }
                }
            },
        });
    }

    onMount(async () => {
        if (browser) {
            await fetchLogRecords();
        }
    });

    $: if (activeTab === 'charts' && !loading && !error && browser) {
        setTimeout(() => {
            if (logRecords.length > 0) {
                createOrUpdateChart();
            } else if (myChart) {
                myChart.destroy();
                myChart = null;
            }
        }, 0);
    }

    onDestroy(() => {
        if (myChart) {
            myChart.destroy();
        }
    });

    async function fetchLogRecords() {
        loading = true;
        error = null;

        const params = new URLSearchParams();
        if (filterCategory) {
            params.append('category', filterCategory);
        }
        if (filterStartDate) {
            params.append('start_date', filterStartDate);
        }
        if (filterEndDate) {
            params.append('end_date', filterEndDate);
        }
        params.append('sort_by', sortBy);
        params.append('sort_order', sortOrder);

        const queryString = params.toString();
        const url = `/api/log_records/${queryString ? `?${queryString}` : ''}`;

        try {
            const response = await authenticatedFetch(url);

            if (response.ok) {
                logRecords = await response.json();
                console.log('Fetched Log Records:', logRecords);
            } else {
                const errorData = await response.json();
                error = `Failed to fetch log records: ${errorData.error || response.statusText}`;
                console.error('Error fetching log records:', errorData);
            }
        } catch (e: any) {
            if (e.message === 'Unauthorized') {
                error = 'Please log in to view reports.';
            } else {
                error = `Network error: ${e.message}`;
            }
            console.error('Network or unexpected error:', e);
        } finally {
            loading = false;
            if (expandedLogId && !logRecords.some(r => r.id === expandedLogId)) {
                expandedLogId = null;
                attachmentsForExpandedLog = [];
            }
        }
    }

    async function toggleAttachments(logId: number) {
        if (expandedLogId === logId) {
            expandedLogId = null;
            attachmentsForExpandedLog = [];
        } else {
            expandedLogId = logId;
            attachmentsForExpandedLog = [];
            fetchingAttachments = true;
            attachmentsError = null;
            try {
                const response = await authenticatedFetch(`/api/log_records/${logId}/attachments`);
                if (response.ok) {
                    attachmentsForExpandedLog = await response.json();
                } else {
                    const errorData = await response.json();
                    attachmentsError = `Failed to fetch attachments: ${errorData.error || response.statusText}`;
                    console.error('Error fetching attachments:', errorData);
                }
            } catch (e: any) {
                if (e.message !== 'Unauthorized') {
                    attachmentsError = `Network error fetching attachments: ${e.message}`;
                } else {
                    attachmentsError = 'Please log in to view attachments.';
                }
                console.error('Network error fetching attachments:', e);
            } finally {
                fetchingAttachments = false;
            }
        }
    }

    function getDownloadUrl(storedFilename: string): string {
        return `${FLASK_API_BASE_URL}/api/attachments/${storedFilename}`;
    }

    function editLogRecord(logId: number) {
        if (browser) {
            goto(`/log-entry?id=${logId}`);
        }
    }

    async function deleteLogRecord(logId: number) {
        if (!confirm('Are you sure you want to delete this log record and all its attachments? This action cannot be undone.')) {
            return;
        }

        try {
            const response = await authenticatedFetch(`/api/log_records/${logId}`, {
                method: 'DELETE',
            });

            if (response.ok) {
                const result = await response.json();
                console.log('Log record deleted successfully:', result);
                alert('Log Record Deleted Successfully!');
                await fetchLogRecords();
            } else {
                const errorData = await response.json();
                console.error('Error deleting log record:', errorData);
                alert(`Failed to delete log record: ${errorData.error || response.statusText}`);
            }
        } catch (error) {
            if (error.message !== 'Unauthorized') {
                console.error('Network or unexpected error during deletion:', error);
                alert('An unexpected error occurred while trying to delete the log record.');
            }
        }
    }

    function applyFiltersAndSort() {
        fetchLogRecords();
    }

    function clearFilters() {
        filterCategory = '';
        filterStartDate = '';
        filterEndDate = '';
        sortBy = 'date_of_incident';
        sortOrder = 'desc';
        fetchLogRecords();
    }

    function formatDate(dateString: string): string {
        if (!dateString) return 'N/A';
        try {
            const options: Intl.DateTimeFormatOptions = { year: 'numeric', month: 'long', day: 'numeric' };
            return new Date(dateString).toLocaleDateString(undefined, options);
        } catch (e) {
            return dateString;
        }
    }

    // --- Summary View Calculations ---
    $: totalIncidents = logRecords.length;
    $: incidentsByCategory = logRecords.reduce((acc, record) => {
        acc[record.category] = (acc[record.category] || 0) + 1;
        return acc;
    }, {} as Record<string, number>);

    // --- Chart Data for Incidents by Category ---
    $: categoryChartLabels = Object.keys(incidentsByCategory);
    $: categoryChartDataValues = Object.values(incidentsByCategory);

    function exportData() {
        alert('Export Data functionality will be implemented later!');
    }
</script>

<svelte:head>
    <title>Log Reports - TrustLog</title>
</svelte:head>

<div class="page-container">
    <header class="header">
        <a href="/" class="back-button">← Back</a>
        <h1>Log Reports</h1>
    </header>

    <div class="filter-controls">
        <button on:click={() => (showFilters = !showFilters)} class="filter-toggle-button">
            {showFilters ? 'Hide Filters' : 'Show Filters'} <span class="icon">{showFilters ? '▲' : '▼'}</span>
        </button>

        {#if showFilters}
            <div class="filter-panel" transition:slide>
                <div class="form-group-inline">
                    <label for="filterCategory">Category:</label>
                    <select id="filterCategory" bind:value={filterCategory} class="filter-input">
                        <option value="">All Categories</option>
                        {#each categories as cat}
                            <option value={cat}>{cat}</option>
                        {/each}
                    </select>
                </div>
                <div class="form-group-inline">
                    <label for="filterStartDate">From Date:</label>
                    <input type="date" id="filterStartDate" bind:value={filterStartDate} class="filter-input" />
                </div>
                <div class="form-group-inline">
                    <label for="filterEndDate">To Date:</label>
                    <input type="date" id="filterEndDate" bind:value={filterEndDate} class="filter-input" />
                </div>

                <div class="form-group-inline">
                    <label for="sortBy">Sort By:</label>
                    <select id="sortBy" bind:value={sortBy} class="filter-input">
                        <option value="date_of_incident">Date of Incident</option>
                        <option value="category">Category</option>
                        <option value="created_at">Log Creation Date</option>
                    </select>
                </div>
                <div class="form-group-inline">
                    <label for="sortOrder">Order:</label>
                    <select id="sortOrder" bind:value={sortOrder} class="filter-input">
                        <option value="desc">Descending</option>
                        <option value="asc">Ascending</option>
                    </select>
                </div>

                <div class="filter-actions">
                    <button on:click={applyFiltersAndSort} class="apply-filters-button">Apply Filters</button>
                    <button on:click={clearFilters} class="clear-filters-button">Clear Filters</button>
                </div>
            </div>
        {/if}
    </div>

    <div class="tabs">
        <button on:click={() => (activeTab = 'summary')} class:active={activeTab === 'summary'}>Summary View</button>
        <button on:click={() => (activeTab = 'detailed')} class:active={activeTab === 'detailed'}>Detailed View</button>
        <button on:click={() => (activeTab = 'charts')} class:active={activeTab === 'charts'}>Charts</button>
    </div>

    {#if loading}
        <p class="status-message">Loading reports...</p>
    {:else if error}
        <p class="error-message">{error}</p>
    {:else if logRecords.length === 0}
        <p class="status-message">No log records found matching your criteria. Try adjusting filters or add some entries first!</p>
    {:else}
        <div class="report-content">
            {#if activeTab === 'summary'}
                <div class="summary-view">
                    <h2>Summary</h2>
                    <p>Total Incidents: <strong>{totalIncidents}</strong></p>
                    <h3>Incidents by Category:</h3>
                    <ul>
                        {#each Object.entries(incidentsByCategory) as [category, count]}
                            <li>{category}: {count}</li>
                        {/each}
                    </ul>
                </div>
            {:else if activeTab === 'detailed'}
                <div class="detailed-view">
                    <h2>Detailed Log Entries</h2>
                    {#each logRecords as record (record.id)}
                        <div class="log-card">
                            <p><strong>Date:</strong> {formatDate(record.date_of_incident)}</p>
                            <p><strong>Category:</strong> {record.category}</p>
                            <p><strong>Description:</strong> {record.description_of_incident}</p>
                            <p><strong>Impact Types:</strong>
                                {#if record.impact_types && record.impact_types.length > 0}
                                    {record.impact_types.join(', ')}
                                {:else}
                                    N/A
                                {/if}
                            </p>
                            {#if record.impact_details}
                                <p><strong>Impact Details:</strong> {record.impact_details}</p>
                            {/if}
                            {#if record.supporting_evidence_snippet}
                                <p><strong>Evidence Snippet:</strong> {record.supporting_evidence_snippet}</p>
                            {/if}
                            {#if record.exhibit_reference}
                                <p><strong>Exhibit:</strong> {record.exhibit_reference}</p>
                            {/if}
                            <p class="meta-data">Logged on: {formatDate(record.created_at)}</p>
                            <p class="meta-data attachment-count-display">
                                Attachments: {record.attachment_count}
                                {#if record.attachment_count > 0}
                                    <button class="toggle-attachments-button" on:click={() => toggleAttachments(record.id)}>
                                        {expandedLogId === record.id ? 'Hide' : 'View'}
                                    </button>
                                {/if}
                            </p>

                            {#if expandedLogId === record.id}
                                <div class="attachments-list" transition:slide>
                                    <h3>Attached Files:</h3>
                                    {#if fetchingAttachments}
                                        <p>Loading attachments...</p>
                                    {:else if attachmentsError}
                                        <p class="error-message">{attachmentsError}</p>
                                    {:else if attachmentsForExpandedLog.length === 0}
                                        <p>No attachments found for this record.</p>
                                    {:else}
                                        <ul>
                                            {#each attachmentsForExpandedLog as attachment (attachment.id)}
                                                <li>
                                                    {attachment.filename} ({ (attachment.filesize_bytes / 1024).toFixed(1) } KB)
                                                    <a href={getDownloadUrl(attachment.stored_filename)} target="_blank" download={attachment.filename}>Download</a>
                                                </li>
                                            {/each}
                                        </ul>
                                    {/if}
                                </div>
                            {/if}
                            <div class="log-card-actions">
                                <button class="edit-button" on:click={() => editLogRecord(record.id)}>Edit</button>
                                <button class="delete-button" on:click={() => deleteLogRecord(record.id)}>Delete</button>
                            </div>
                        </div>
                    {/each}
                </div>
            {:else if activeTab === 'charts'}
                <div class="charts-view">
                    <h2>Charts</h2>
                    <div class="chart-container">
                        {#if categoryChartDataValues.length > 0}
                            <canvas bind:this={chartCanvas}></canvas>
                        {:else}
                            <p>No data available to generate charts. Add some log entries first.</p>
                        {/if}
                    </div>
                </div>
            {/if}
        </div>
    {/if}

    {#if logRecords.length > 0}
        <div class="button-group export-button-group">
            <button on:click={exportData} class="export-button">Export Data</button>
        </div>
    {/if}
</div>

<style>
    .page-container {
        padding: 1rem;
        max-width: 800px;
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

    /* Filter Panel Styles */
    .filter-controls {
        margin-bottom: 1.5rem;
        padding: 0.5rem 0;
        border-bottom: 1px solid #eee;
    }

    .filter-toggle-button {
        background-color: #f0f0f0;
        color: #333;
        border: 1px solid #ccc;
        padding: 0.7rem 1.2rem;
        border-radius: 5px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        font-size: 1rem;
        transition: background-color 0.2s ease;
    }

    .filter-toggle-button:hover {
        background-color: #e0e0e0;
    }

    .filter-toggle-button .icon {
        margin-left: 0.5rem;
    }

    .filter-panel {
        padding: 1rem;
        background-color: #f9f9f9;
        border: 1px solid #eee;
        border-radius: 8px;
        margin-top: 1rem;
        display: grid;
        gap: 1rem;
        grid-template-columns: 1fr;
    }

    .form-group-inline {
        display: flex;
        flex-direction: column;
    }

    .form-group-inline label {
        font-weight: bold;
        margin-bottom: 0.3rem;
        color: #555;
        font-size: 0.9rem;
    }

    .filter-input {
        width: 100%;
        padding: 0.6rem;
        border: 1px solid #ccc;
        border-radius: 4px;
        box-sizing: border-box;
        font-size: 0.9rem;
    }

    .filter-actions {
        display: flex;
        flex-direction: column;
        gap: 0.8rem;
        margin-top: 0.5rem;
    }

    .apply-filters-button, .clear-filters-button {
        padding: 0.7rem 1rem;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        font-size: 1rem;
        transition: background-color 0.2s ease;
    }

    .apply-filters-button {
        background-color: #007bff;
        color: white;
    }
    .apply-filters-button:hover {
        background-color: #0056b3;
    }

    .clear-filters-button {
        background-color: #6c757d;
        color: white;
    }
    .clear-filters-button:hover {
        background-color: #5a6268;
    }

    /* Tabs and Report Content */
    .tabs {
        display: flex;
        justify-content: space-around;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid #ddd;
    }

    .tabs button {
        flex-grow: 1;
        padding: 0.8rem 1rem;
        border: none;
        background-color: transparent;
        cursor: pointer;
        font-size: 1rem;
        color: #555;
        border-bottom: 3px solid transparent;
        transition: all 0.2s ease-in-out;
    }

    .tabs button.active {
        color: #007bff;
        border-bottom-color: #007bff;
        font-weight: bold;
    }

    .tabs button:hover {
        background-color: #f0f0f0;
    }

    .report-content {
        background-color: #fff;
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
    }

    .log-card {
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        padding: 1rem;
        margin-bottom: 1rem;
        background-color: #f9f9f9;
    }

    .log-card p {
        margin: 0.3rem 0;
        line-height: 1.4;
    }

    .log-card strong {
        color: #333;
    }

    .log-card .meta-data {
        font-size: 0.85rem;
        color: #777;
        text-align: right;
        margin-top: 0.8rem;
    }

    .status-message {
        text-align: center;
        padding: 1rem;
        color: #666;
    }

    .error-message {
        color: red;
        font-weight: bold;
        text-align: center;
        padding: 1rem;
    }

    .export-button-group {
        display: flex;
        justify-content: flex-end;
        margin-top: 2rem;
    }

    .export-button {
        padding: 0.8rem 1.5rem;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        font-size: 1rem;
        transition: background-color 0.2s ease;
    }

    .export-button:hover {
        background-color: #0056b3;
    }

    .summary-view h2, .detailed-view h2, .charts-view h2 {
        color: #007bff;
        margin-bottom: 1rem;
    }

    .summary-view ul {
        list-style-type: none;
        padding: 0;
    }

    .summary-view li {
        padding: 0.5rem 0;
        border-bottom: 1px dashed #eee;
    }

    .chart-container {
        position: relative;
        height: 400px;
        width: 100%;
        margin-top: 1.5rem;
        background-color: #fcfcfc;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: inset 0 0 5px rgba(0,0,0,0.05);
    }

    .charts-view p {
        text-align: center;
        margin-top: 1rem;
        color: #666;
    }

    /* Styles for attachment list */
    .toggle-attachments-button {
        background-color: #e0e0e0;
        color: #333;
        border: 1px solid #ccc;
        padding: 0.2rem 0.5rem;
        border-radius: 3px;
        cursor: pointer;
        font-size: 0.75rem;
        margin-left: 0.5rem;
        transition: background-color 0.2s ease;
    }

    .toggle-attachments-button:hover {
        background-color: #d0d0d0;
    }

    .attachments-list {
        background-color: #f2f2f2;
        border-left: 3px solid #007bff;
        padding: 0.8rem 1rem;
        margin-top: 1rem;
        border-radius: 4px;
    }

    .attachments-list h3 {
        font-size: 1rem;
        color: #444;
        margin-top: 0;
        margin-bottom: 0.8rem;
    }

    .attachments-list ul {
        list-style-type: none;
        padding: 0;
        margin: 0;
    }

    .attachments-list li {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.4rem 0;
        border-bottom: 1px dashed #e0e0e0;
        font-size: 0.9rem;
    }

    .attachments-list li:last-child {
        border-bottom: none;
    }

    .attachments-list li a {
        color: #007bff;
        text-decoration: none;
        margin-left: 1rem;
        white-space: nowrap;
    }

    .attachments-list li a:hover {
        text-decoration: underline;
    }

    /* New styles for edit/delete buttons */
    .log-card-actions {
        display: flex;
        justify-content: flex-end;
        gap: 0.5rem;
        margin-top: 1rem;
        padding-top: 0.8rem;
        border-top: 1px solid #eee;
    }

    .log-card-actions button {
        padding: 0.5rem 1rem;
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.9rem;
        transition: background-color 0.2s ease;
    }

    .edit-button {
        background-color: #17a2b8;
        color: white;
        border: none;
    }

    .edit-button:hover {
        background-color: #138496;
    }

    .delete-button {
        background-color: #dc3545;
        color: white;
        border: none;
    }

    .delete-button:hover {
        background-color: #c82333;
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

        .filter-panel {
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        }

        .filter-actions {
            flex-direction: row;
            justify-content: flex-end;
            grid-column: 1 / -1;
        }
    }
</style>