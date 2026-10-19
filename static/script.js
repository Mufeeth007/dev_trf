/**
 * Developer Activity Tracker - Frontend Application
 * Plain Vanilla JavaScript (ES6+)
 */

document.addEventListener("DOMContentLoaded", () => {
    // ==========================================================================
    // Application State
    // ==========================================================================
    const state = {
        activities: [],
        stats: { total: 0, success: 0, pending: 0, failed: 0 },
        searchQuery: "",
        statusFilter: "All",
        sortOrder: "newest",
        editingId: null,
        deletingItem: null,
        health: {
            ferretdb: false,
            redis: false,
        },
    };

    // ==========================================================================
    // DOM Element References
    // ==========================================================================
    const elements = {
        // Form elements
        activityForm: document.getElementById("activity-form"),
        editActivityId: document.getElementById("edit-activity-id"),
        formHeading: document.getElementById("form-action-title"),
        formIcon: document.getElementById("form-action-icon"),
        formModeBadge: document.getElementById("form-mode-badge"),
        btnSubmitForm: document.getElementById("btn-submit-form"),
        btnSubmitText: document.getElementById("btn-submit-text"),
        btnCancelEdit: document.getElementById("btn-cancel-edit"),

        // Form inputs
        projectNameInput: document.getElementById("project_name"),
        titleInput: document.getElementById("title"),
        developerNameInput: document.getElementById("developer_name"),
        statusInput: document.getElementById("status"),
        descriptionInput: document.getElementById("description"),

        // Input error containers
        errProjectName: document.getElementById("err-project_name"),
        errTitle: document.getElementById("err-title"),
        errDeveloperName: document.getElementById("err-developer_name"),
        errStatus: document.getElementById("err-status"),
        errDescription: document.getElementById("err-description"),

        // Summary cards
        statTotal: document.getElementById("stat-total"),
        statSuccess: document.getElementById("stat-success"),
        statPending: document.getElementById("stat-pending"),
        statFailed: document.getElementById("stat-failed"),

        // Toolbar controls
        searchInput: document.getElementById("search-input"),
        btnClearSearch: document.getElementById("btn-clear-search"),
        statusFilter: document.getElementById("status-filter"),
        sortOrder: document.getElementById("sort-order"),
        btnGlobalRefresh: document.getElementById("btn-global-refresh"),

        // Cache badge
        cacheBadge: document.getElementById("cache-source-badge"),
        cacheIcon: document.getElementById("cache-icon"),
        cacheSourceText: document.getElementById("cache-source-text"),

        // Health indicators
        ferretDot: document.getElementById("ferretdb-dot"),
        ferretVal: document.getElementById("ferretdb-val"),
        redisDot: document.getElementById("redis-dot"),
        redisVal: document.getElementById("redis-val"),
        dbErrorBanner: document.getElementById("db-error-banner"),
        dbErrorMessage: document.getElementById("db-error-message"),

        // Table & states
        tableBody: document.getElementById("activities-table-body"),
        emptyState: document.getElementById("empty-state"),
        emptyStateMessage: document.getElementById("empty-state-message"),
        loadingState: document.getElementById("loading-state"),

        // Toast container
        toastContainer: document.getElementById("toast-container"),

        // Modal elements
        deleteModal: document.getElementById("delete-modal"),
        btnModalClose: document.getElementById("btn-modal-close"),
        btnModalCancel: document.getElementById("btn-modal-cancel"),
        btnModalConfirmDelete: document.getElementById("btn-modal-confirm-delete"),
        delPreviewProject: document.getElementById("del-preview-project"),
        delPreviewTitle: document.getElementById("del-preview-title"),
        delPreviewId: document.getElementById("del-preview-id"),
    };

    // ==========================================================================
    // Toast Notification System
    // ==========================================================================
    function showToast(message, type = "success") {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;

        const icon = type === "success" ? "✅" : type === "error" ? "❌" : "ℹ️";

        toast.innerHTML = `
            <div class="toast-content">
                <strong>${icon}</strong> ${escapeHtml(message)}
            </div>
            <button class="toast-close" aria-label="Dismiss">&times;</button>
        `;

        const closeBtn = toast.querySelector(".toast-close");
        closeBtn.addEventListener("click", () => {
            dismissToast(toast);
        });

        elements.toastContainer.appendChild(toast);

        // Auto dismiss after 4 seconds
        setTimeout(() => {
            dismissToast(toast);
        }, 4000);
    }

    function dismissToast(toast) {
        if (!toast || toast.classList.contains("toast-fadeout")) return;
        toast.classList.add("toast-fadeout");
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }

    // ==========================================================================
    // Health Check & System Status
    // ==========================================================================
    async function checkSystemHealth() {
        try {
            const res = await fetch("/api/health");
            const data = await res.json();

            const isFerretOk = data.ferretdb && data.ferretdb.status === "connected";
            const isRedisOk = data.redis && data.redis.status === "connected";

            state.health.ferretdb = isFerretOk;
            state.health.redis = isRedisOk;

            // Update FerretDB status badge
            if (isFerretOk) {
                elements.ferretDot.className = "status-dot dot-connected";
                elements.ferretVal.textContent = "Connected";
                elements.dbErrorBanner.style.display = "none";
            } else {
                elements.ferretDot.className = "status-dot dot-disconnected";
                elements.ferretVal.textContent = "Offline";
                elements.dbErrorBanner.style.display = "block";
                elements.dbErrorMessage.textContent =
                    data.ferretdb?.error || "FerretDB service is currently unavailable. Please verify FerretDB is running.";
            }

            // Update Redis status badge
            if (isRedisOk) {
                elements.redisDot.className = "status-dot dot-connected";
                elements.redisVal.textContent = "Active";
            } else {
                elements.redisDot.className = "status-dot dot-disconnected";
                elements.redisVal.textContent = "Offline (Bypassed)";
            }
        } catch (err) {
            console.error("Health check request failed:", err);
            elements.ferretDot.className = "status-dot dot-disconnected";
            elements.ferretVal.textContent = "Error";
            elements.redisDot.className = "status-dot dot-disconnected";
            elements.redisVal.textContent = "Error";
            elements.dbErrorBanner.style.display = "block";
            elements.dbErrorMessage.textContent = "Unable to connect to Flask server.";
        }
    }

    // ==========================================================================
    // API Requests
    // ==========================================================================
    async function fetchStats() {
        try {
            const res = await fetch("/api/dashboard/stats");
            const result = await res.json();

            if (result.success && result.data) {
                state.stats = result.data;
                renderStats(result.data);
            }
        } catch (err) {
            console.error("Error fetching statistics:", err);
        }
    }

    async function fetchActivities() {
        showLoading(true);

        const params = new URLSearchParams();
        if (state.searchQuery.trim()) {
            params.append("search", state.searchQuery.trim());
        }
        if (state.statusFilter && state.statusFilter !== "All") {
            params.append("status", state.statusFilter);
        }
        if (state.sortOrder) {
            params.append("sort", state.sortOrder);
        }

        try {
            const res = await fetch(`/api/activities?${params.toString()}`);
            const result = await res.json();

            if (result.success) {
                state.activities = result.data || [];
                renderActivities(state.activities);
                updateCacheIndicator(result.cached);
            } else {
                showToast(result.error || "Failed to load activities", "error");
                renderActivities([]);
            }
        } catch (err) {
            console.error("Error fetching activities:", err);
            showToast("Network error while retrieving activities.", "error");
            renderActivities([]);
        } finally {
            showLoading(false);
        }
    }

    // ==========================================================================
    // Render Functions
    // ==========================================================================
    function renderStats(stats) {
        elements.statTotal.textContent = stats.total || 0;
        elements.statSuccess.textContent = stats.success || 0;
        elements.statPending.textContent = stats.pending || 0;
        elements.statFailed.textContent = stats.failed || 0;
    }

    function updateCacheIndicator(isCached) {
        if (isCached) {
            elements.cacheBadge.className = "cache-badge cached";
            elements.cacheIcon.textContent = "⚡";
            elements.cacheSourceText.textContent = "Redis Cached (TTL 60s)";
        } else {
            elements.cacheBadge.className = "cache-badge direct";
            elements.cacheIcon.textContent = "🗄️";
            elements.cacheSourceText.textContent = "FerretDB Direct";
        }
    }

    function showLoading(isLoading) {
        if (isLoading) {
            elements.loadingState.style.display = "block";
            elements.tableBody.innerHTML = "";
            elements.emptyState.style.display = "none";
        } else {
            elements.loadingState.style.display = "none";
        }
    }

    function renderActivities(activities) {
        elements.tableBody.innerHTML = "";

        if (!activities || activities.length === 0) {
            elements.emptyState.style.display = "block";

            if (state.searchQuery.trim() || state.statusFilter !== "All") {
                elements.emptyStateMessage.textContent =
                    "No activities match your current search or status filter criteria.";
            } else {
                elements.emptyStateMessage.textContent =
                    "No activities recorded yet. Add your first developer activity using the form on the left!";
            }
            return;
        }

        elements.emptyState.style.display = "none";

        activities.forEach((act) => {
            const tr = document.createElement("tr");

            // Format status badge class
            const statusLower = (act.status || "").toLowerCase();
            const badgeClass =
                statusLower === "success"
                    ? "badge-success"
                    : statusLower === "failed"
                    ? "badge-failed"
                    : "badge-pending";

            // Format date display
            const formattedDate = act.created_at || "Just now";

            tr.innerHTML = `
                <td>
                    <span class="id-badge" title="${escapeHtml(act.id)}">
                        ${escapeHtml(act.id.substring(0, 8))}...
                    </span>
                </td>
                <td>
                    <span class="table-project-name">${escapeHtml(act.project_name)}</span>
                </td>
                <td>
                    <span class="table-title">${escapeHtml(act.title)}</span>
                </td>
                <td>
                    <span class="table-dev">${escapeHtml(act.developer_name)}</span>
                </td>
                <td>
                    <span class="badge ${badgeClass}">${escapeHtml(act.status)}</span>
                </td>
                <td>
                    <span class="table-time">${escapeHtml(formattedDate)}</span>
                </td>
                <td>
                    <div class="table-desc" title="${escapeHtml(act.description)}">
                        ${escapeHtml(act.description)}
                    </div>
                </td>
                <td style="text-align: center;">
                    <div class="action-buttons">
                        <button
                            type="button"
                            class="btn-icon-action btn-icon-edit"
                            data-id="${escapeHtml(act.id)}"
                            title="Edit this activity"
                        >
                            ✏️ Edit
                        </button>
                        <button
                            type="button"
                            class="btn-icon-action btn-icon-delete"
                            data-id="${escapeHtml(act.id)}"
                            data-title="${escapeHtml(act.title)}"
                            data-project="${escapeHtml(act.project_name)}"
                            title="Delete this activity"
                        >
                            🗑️ Delete
                        </button>
                    </div>
                </td>
            `;

            elements.tableBody.appendChild(tr);
        });

        // Attach action listeners
        attachTableActionListeners();
    }

    function attachTableActionListeners() {
        // Edit buttons
        document.querySelectorAll(".btn-icon-edit").forEach((btn) => {
            btn.addEventListener("click", () => {
                const id = btn.getAttribute("data-id");
                startEditActivity(id);
            });
        });

        // Delete buttons
        document.querySelectorAll(".btn-icon-delete").forEach((btn) => {
            btn.addEventListener("click", () => {
                const id = btn.getAttribute("data-id");
                const title = btn.getAttribute("data-title");
                const project = btn.getAttribute("data-project");
                openDeleteModal(id, title, project);
            });
        });
    }

    // ==========================================================================
    // Form Validation & Handling
    // ==========================================================================
    function clearFormErrors() {
        elements.errProjectName.textContent = "";
        elements.errTitle.textContent = "";
        elements.errDeveloperName.textContent = "";
        elements.errStatus.textContent = "";
        elements.errDescription.textContent = "";
    }

    function validateForm() {
        clearFormErrors();
        let isValid = true;

        const projectName = elements.projectNameInput.value.trim();
        const title = elements.titleInput.value.trim();
        const developerName = elements.developerNameInput.value.trim();
        const status = elements.statusInput.value.trim();
        const description = elements.descriptionInput.value.trim();

        if (!projectName) {
            elements.errProjectName.textContent = "Project name is required.";
            isValid = false;
        }

        if (!title) {
            elements.errTitle.textContent = "Activity title is required.";
            isValid = false;
        }

        if (!developerName) {
            elements.errDeveloperName.textContent = "Developer name is required.";
            isValid = false;
        }

        if (!status || !["Success", "Pending", "Failed"].includes(status)) {
            elements.errStatus.textContent = "Please select a valid status.";
            isValid = false;
        }

        if (!description) {
            elements.errDescription.textContent = "Description is required.";
            isValid = false;
        }

        return isValid;
    }

    async function handleFormSubmit(e) {
        e.preventDefault();

        if (!validateForm()) {
            return;
        }

        const payload = {
            project_name: elements.projectNameInput.value.trim(),
            title: elements.titleInput.value.trim(),
            developer_name: elements.developerNameInput.value.trim(),
            status: elements.statusInput.value.trim(),
            description: elements.descriptionInput.value.trim(),
        };

        const isEditing = Boolean(state.editingId);
        const url = isEditing ? `/api/activities/${state.editingId}` : "/api/activities";
        const method = isEditing ? "PUT" : "POST";

        elements.btnSubmitForm.disabled = true;
        elements.btnSubmitText.textContent = isEditing ? "Updating..." : "Saving...";

        try {
            const res = await fetch(url, {
                method: method,
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(payload),
            });

            const result = await res.json();

            if (result.success) {
                showToast(
                    result.message || (isEditing ? "Activity updated successfully" : "Activity created successfully"),
                    "success"
                );
                resetForm();
                await Promise.all([fetchActivities(), fetchStats()]);
            } else {
                if (result.details && typeof result.details === "object") {
                    // Display specific field errors
                    if (result.details.project_name) elements.errProjectName.textContent = result.details.project_name;
                    if (result.details.title) elements.errTitle.textContent = result.details.title;
                    if (result.details.developer_name) elements.errDeveloperName.textContent = result.details.developer_name;
                    if (result.details.status) elements.errStatus.textContent = result.details.status;
                    if (result.details.description) elements.errDescription.textContent = result.details.description;
                }
                showToast(result.error || "Failed to process activity request.", "error");
            }
        } catch (err) {
            console.error("Form submit error:", err);
            showToast("Network error submitting form. Check server status.", "error");
        } finally {
            elements.btnSubmitForm.disabled = false;
            elements.btnSubmitText.textContent = isEditing ? "Update Activity" : "Record Activity";
        }
    }

    function startEditActivity(id) {
        const item = state.activities.find((a) => a.id === id);
        if (!item) return;

        state.editingId = id;
        elements.editActivityId.value = id;

        // Fill form
        elements.projectNameInput.value = item.project_name || "";
        elements.titleInput.value = item.title || "";
        elements.developerNameInput.value = item.developer_name || "";
        elements.statusInput.value = item.status || "Pending";
        elements.descriptionInput.value = item.description || "";

        // Update form UI to Edit mode
        elements.formHeading.textContent = "Edit Activity";
        elements.formIcon.textContent = "✏️";
        elements.formModeBadge.textContent = "Editing";
        elements.btnSubmitText.textContent = "Update Activity";
        elements.btnCancelEdit.style.display = "inline-flex";

        clearFormErrors();

        // Scroll to form smoothly
        elements.activityForm.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function resetForm() {
        state.editingId = null;
        elements.editActivityId.value = "";
        elements.activityForm.reset();

        elements.formHeading.textContent = "Add New Activity";
        elements.formIcon.textContent = "➕";
        elements.formModeBadge.textContent = "New";
        elements.btnSubmitText.textContent = "Record Activity";
        elements.btnCancelEdit.style.display = "none";

        clearFormErrors();
    }

    // ==========================================================================
    // Delete Confirmation Modal
    // ==========================================================================
    function openDeleteModal(id, title, project) {
        state.deletingItem = { id, title, project };

        elements.delPreviewId.textContent = id;
        elements.delPreviewTitle.textContent = title;
        elements.delPreviewProject.textContent = project;

        elements.deleteModal.style.display = "flex";
    }

    function closeDeleteModal() {
        state.deletingItem = null;
        elements.deleteModal.style.display = "none";
    }

    async function confirmDeleteActivity() {
        if (!state.deletingItem) return;

        const id = state.deletingItem.id;
        elements.btnModalConfirmDelete.disabled = true;
        elements.btnModalConfirmDelete.textContent = "Deleting...";

        try {
            const res = await fetch(`/api/activities/${id}`, {
                method: "DELETE",
            });
            const result = await res.json();

            if (result.success) {
                showToast("Activity deleted successfully.", "success");
                closeDeleteModal();

                // If currently editing this item, reset form
                if (state.editingId === id) {
                    resetForm();
                }

                await Promise.all([fetchActivities(), fetchStats()]);
            } else {
                showToast(result.error || "Failed to delete activity.", "error");
            }
        } catch (err) {
            console.error("Delete request error:", err);
            showToast("Network error while deleting activity.", "error");
        } finally {
            elements.btnModalConfirmDelete.disabled = false;
            elements.btnModalConfirmDelete.textContent = "Delete Activity";
        }
    }

    // ==========================================================================
    // Search, Filter, and Sort Event Handlers
    // ==========================================================================
    let searchDebounceTimeout = null;

    elements.searchInput.addEventListener("input", (e) => {
        const val = e.target.value;
        state.searchQuery = val;

        elements.btnClearSearch.style.display = val ? "block" : "none";

        clearTimeout(searchDebounceTimeout);
        searchDebounceTimeout = setTimeout(() => {
            fetchActivities();
        }, 300);
    });

    elements.btnClearSearch.addEventListener("click", () => {
        elements.searchInput.value = "";
        state.searchQuery = "";
        elements.btnClearSearch.style.display = "none";
        fetchActivities();
    });

    elements.statusFilter.addEventListener("change", (e) => {
        state.statusFilter = e.target.value;
        fetchActivities();
    });

    elements.sortOrder.addEventListener("change", (e) => {
        state.sortOrder = e.target.value;
        fetchActivities();
    });

    elements.btnGlobalRefresh.addEventListener("click", async () => {
        elements.btnGlobalRefresh.textContent = "Refreshing...";
        await Promise.all([checkSystemHealth(), fetchStats(), fetchActivities()]);
        elements.btnGlobalRefresh.textContent = "🔄 Refresh";
        showToast("Dashboard data refreshed.", "info");
    });

    // Modal listeners
    elements.btnModalClose.addEventListener("click", closeDeleteModal);
    elements.btnModalCancel.addEventListener("click", closeDeleteModal);
    elements.btnModalConfirmDelete.addEventListener("click", confirmDeleteActivity);

    // Close modal on backdrop click
    elements.deleteModal.addEventListener("click", (e) => {
        if (e.target === elements.deleteModal) {
            closeDeleteModal();
        }
    });

    // Form listeners
    elements.activityForm.addEventListener("submit", handleFormSubmit);
    elements.btnCancelEdit.addEventListener("click", resetForm);

    // ==========================================================================
    // Utility Helpers
    // ==========================================================================
    function escapeHtml(str) {
        if (!str && str !== 0) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // ==========================================================================
    // Initial Load & Health Polling
    // ==========================================================================
    async function init() {
        await checkSystemHealth();
        await fetchStats();
        await fetchActivities();

        // Check health every 15 seconds to reflect database or Redis status changes
        setInterval(checkSystemHealth, 15000);
    }

    init();
});
