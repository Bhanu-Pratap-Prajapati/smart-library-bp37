const API_BASE_URL = "http://127.0.0.1:5000/api";
const PROFILE_CACHE_PREFIX = "smartLibraryProfileCache";
const DEFAULT_PROFILE_BIO = "Add a short bio from the profile editor.";
let duePromptInProgress = false;
let activeProfileImageUrl = "";
let activeBioText = "";

function headers() {
    const token = localStorage.getItem("smartLibraryToken");
    return token
        ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` }
        : { "Content-Type": "application/json" };
}

function esc(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function alertNodes() {
    return {
        modal: document.getElementById("dashboardAlertModal"),
        title: document.getElementById("dashboardAlertTitle"),
        message: document.getElementById("dashboardAlertMessage"),
        cancel: document.getElementById("dashboardAlertCancel"),
        confirm: document.getElementById("dashboardAlertConfirm"),
    };
}

function closeAlertModal() {
    const { modal } = alertNodes();
    if (modal) {
        modal.classList.remove("open");
    }
}

function showAlertModal({
    title = "Notification",
    message = "",
    confirmText = "OK",
    cancelText = "",
    showCancel = false,
    onConfirm = null,
    onCancel = null,
}) {
    const nodes = alertNodes();
    if (!nodes.modal || !nodes.title || !nodes.message || !nodes.cancel || !nodes.confirm) {
        return;
    }
    nodes.title.textContent = title;
    nodes.message.textContent = message;
    nodes.confirm.textContent = confirmText;
    nodes.cancel.textContent = cancelText || "Cancel";
    nodes.cancel.style.display = showCancel ? "inline-flex" : "none";

    nodes.confirm.onclick = () => {
        closeAlertModal();
        if (typeof onConfirm === "function") {
            onConfirm();
        }
    };
    nodes.cancel.onclick = () => {
        closeAlertModal();
        if (typeof onCancel === "function") {
            onCancel();
        }
    };

    nodes.modal.classList.add("open");
}

function showInfoPopup(message, title = "Notification", confirmText = "OK") {
    return new Promise((resolve) => {
        showAlertModal({
            title,
            message,
            confirmText,
            showCancel: false,
            onConfirm: () => resolve(true),
        });
    });
}

function showConfirmPopup(message, title = "Confirm", confirmText = "Confirm", cancelText = "Cancel") {
    return new Promise((resolve) => {
        showAlertModal({
            title,
            message,
            confirmText,
            cancelText,
            showCancel: true,
            onConfirm: () => resolve(true),
            onCancel: () => resolve(false),
        });
    });
}

function getProfileCacheKey() {
    const user = JSON.parse(localStorage.getItem("smartLibraryUser") || "null");
    if (!user) {
        return `${PROFILE_CACHE_PREFIX}:anonymous`;
    }
    const idPart = user.id ? `id:${user.id}` : "";
    const emailPart = user.email ? `email:${String(user.email).toLowerCase()}` : "";
    return `${PROFILE_CACHE_PREFIX}:${idPart || emailPart || "anonymous"}`;
}

function readProfileCache() {
    try {
        const raw = localStorage.getItem(getProfileCacheKey());
        if (!raw) {
            return {};
        }
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === "object" ? parsed : {};
    } catch (_error) {
        return {};
    }
}

function writeProfileCache(patch) {
    const current = readProfileCache();
    const next = { ...current, ...(patch || {}) };
    localStorage.setItem(getProfileCacheKey(), JSON.stringify(next));
}

function renderStats(stats) {
    const node = document.getElementById("statsGrid");
    node.innerHTML = `<div class="grid grid-auto">${(stats || []).map((item) => `
        <article class="media-card">
            <div class="media-content">
                <strong>${esc(item.value)}</strong>
                <p class="small">${esc(item.label)}</p>
            </div>
        </article>
    `).join("")}</div>`;
}

function renderActivities(activities) {
    const body = document.getElementById("activityBody");
    if (!activities || !activities.length) {
        body.innerHTML = '<tr><td colspan="6">No records.</td></tr>';
        return;
    }
    body.innerHTML = activities.map((row) => `
        <tr>
            <td>${esc(row.title)}</td>
            <td>${esc(row.author)}</td>
            <td>${esc(row.issued_at)}</td>
            <td>${esc(row.due_at)}</td>
            <td>${esc(row.returned_at)}</td>
            <td>${esc(row.fine_amount)}</td>
        </tr>
    `).join("");
}

function renderNotifications(notifications, isStudent) {
    const section = document.getElementById("notificationsSection");
    const list = document.getElementById("notificationsList");
    if (!section || !list) {
        return;
    }
    if (!isStudent) {
        section.style.display = "none";
        return;
    }
    section.style.display = "block";

    if (!notifications || !notifications.length) {
        list.innerHTML = '<p class="small">No issue or due alerts right now.</p>';
        return;
    }

    list.innerHTML = notifications.map((item) => `
        <article class="media-card">
            <div class="media-content grid" style="gap:8px;">
                <strong>${esc(item.title)}</strong>
                <p class="small">${esc(item.message)}</p>
                ${item.can_return && item.book_id && item.transaction_id ? `
                    <div class="actions">
                        <button class="btn btn-secondary" type="button" data-action="return-book" data-book-id="${item.book_id}" data-transaction-id="${item.transaction_id}">Return Book</button>
                    </div>
                ` : ""}
            </div>
        </article>
    `).join("");
}

function renderActiveLoans(loans, isStudent) {
    const section = document.getElementById("activeLoansSection");
    const list = document.getElementById("activeLoansList");
    if (!section || !list) {
        return;
    }
    if (!isStudent) {
        section.style.display = "none";
        return;
    }
    section.style.display = "block";

    const activeIssued = (loans || []).filter((loan) => String(loan.status || "").toLowerCase() === "issued");

    if (!activeIssued.length) {
        list.innerHTML = '<p class="small">No active issued books.</p>';
        return;
    }

    list.innerHTML = activeIssued.map((loan) => `
        <article class="media-card">
            <div class="media-content grid" style="gap:8px;">
                <strong>${esc(loan.title)}</strong>
                <p class="small">${esc(loan.author_name)}</p>
                <p class="small">Issued: ${esc(loan.issued_at)}</p>
                <p class="small">Due: ${esc(loan.due_at)}</p>
                <p class="small">Status: ${esc(loan.status)}</p>
                <div class="actions">
                    <button class="btn btn-secondary" type="button" data-action="return-book" data-book-id="${loan.book_id}" data-transaction-id="${loan.transaction_id || ""}" ${loan.transaction_id ? "" : "disabled"}>Return Book</button>
                </div>
            </div>
        </article>
    `).join("");
}

function renderUsers(management) {
    const section = document.getElementById("adminUsersSection");
    const body = document.getElementById("usersBody");
    const summary = document.getElementById("usersSummary");

    if (!management || !management.users || !management.users.length) {
        section.style.display = "none";
        return;
    }

    section.style.display = "block";
    summary.innerHTML = (management.summary || []).map((item) => `<span class="badge">${esc(item.label)}: ${esc(item.value)}</span>`).join(" ");
    body.innerHTML = management.users.map((user) => `
        <tr>
            <td>${esc(user.full_name)}</td>
            <td>${esc(user.email)}</td>
            <td>${esc(user.role)}</td>
            <td>${esc(user.status)}</td>
            <td>
                <select class="input user-status" data-id="${user.id}">
                    <option value="active" ${user.status.toLowerCase() === "active" ? "selected" : ""}>Active</option>
                    <option value="inactive" ${user.status.toLowerCase() === "inactive" ? "selected" : ""}>Inactive</option>
                </select>
            </td>
        </tr>
    `).join("");
}

function fillProfile(profile, dashboard) {
    const cached = readProfileCache();
    const cachedBio = String(cached.bio || "").trim();
    const cachedImageUrl = String(cached.profile_image_url || "").trim();
    const profileBio = String(profile.bio || "").trim();
    const resolvedBio = (!profileBio || profileBio === DEFAULT_PROFILE_BIO) && cachedBio ? cachedBio : profileBio;
    const resolvedImage = String(profile.profile_image_url || "").trim() || cachedImageUrl;

    document.getElementById("dashboardTitle").textContent = dashboard.headline;
    document.getElementById("dashboardSubtitle").textContent = dashboard.subheadline;
    document.getElementById("profileName").textContent = profile.full_name;
    document.getElementById("profileMeta").textContent = `${profile.profession_title} | ${profile.role}`;
    document.getElementById("profileEmail").textContent = profile.email;
    document.getElementById("profileDept").textContent = profile.department;
    document.getElementById("profileBio").textContent = resolvedBio || DEFAULT_PROFILE_BIO;
    const bioInput = document.getElementById("bioInputInline");
    if (bioInput) {
        bioInput.value = resolvedBio || "";
    }
    activeProfileImageUrl = resolvedImage;
    activeBioText = resolvedBio || "";

    const avatar = document.getElementById("profileAvatar");
    avatar.textContent = profile.initials;
    avatar.style.background = profile.avatar_color || "#2563eb";
    if (resolvedImage) {
        avatar.innerHTML = `<img src="${esc(resolvedImage)}" alt="Profile" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
    }

    writeProfileCache({
        bio: resolvedBio || "",
        profile_image_url: String(profile.profile_image_url || "").trim() || cachedImageUrl,
    });

    setBioEditMode(false);
}

function setBioEditMode(isEditing) {
    const bioDisplay = document.getElementById("profileBio");
    const editButton = document.getElementById("editBioButton");
    const bioEditor = document.getElementById("bioEditor");
    const bioInput = document.getElementById("bioInputInline");
    if (!bioDisplay || !editButton || !bioEditor || !bioInput) {
        return;
    }
    bioDisplay.style.display = isEditing ? "none" : "block";
    editButton.style.display = isEditing ? "none" : "inline-flex";
    bioEditor.style.display = isEditing ? "grid" : "none";
    if (isEditing) {
        bioInput.focus();
        bioInput.selectionStart = bioInput.value.length;
        bioInput.selectionEnd = bioInput.value.length;
    }
}

async function loadDashboard() {
    const token = localStorage.getItem("smartLibraryToken");
    if (!token) {
        window.location.href = "login.html";
        return;
    }

    const response = await fetch(`${API_BASE_URL}/me/dashboard`, { headers: headers(), cache: "no-store" });
    const result = await response.json();
    if (!response.ok || !result.success) {
        localStorage.removeItem("smartLibraryToken");
        localStorage.removeItem("smartLibraryUser");
        window.location.href = "login.html";
        return;
    }

    fillProfile(result.data.profile, result.data.dashboard);
    renderStats(result.data.dashboard.stats || []);
    renderActivities(result.data.dashboard.activities || []);
    const isStudent = String(result.data.profile?.role || "").toLowerCase() === "student";
    renderNotifications(result.data.dashboard.notifications || [], isStudent);
    renderActiveLoans(result.data.dashboard.active_loans || [], isStudent);
    renderUsers(result.data.management);
    if (isStudent) {
        await checkDueBooksAndPrompt();
    }
}

function beginBioEdit() {
    const msg = document.getElementById("profileMessage");
    const bioInput = document.getElementById("bioInputInline");
    if (msg) {
        msg.textContent = "";
        msg.className = "form-message";
    }
    if (bioInput) {
        bioInput.value = activeBioText || "";
    }
    setBioEditMode(true);
}

function cancelBioEdit() {
    const bioInput = document.getElementById("bioInputInline");
    const bioDisplay = document.getElementById("profileBio");
    const msg = document.getElementById("profileMessage");
    if (bioInput) {
        bioInput.value = activeBioText || "";
    }
    if (bioDisplay) {
        bioDisplay.textContent = activeBioText || DEFAULT_PROFILE_BIO;
    }
    if (msg) {
        msg.textContent = "";
        msg.className = "form-message";
    }
    setBioEditMode(false);
}

async function saveBioInline() {
    const bioInput = document.getElementById("bioInputInline");
    const bioDisplay = document.getElementById("profileBio");
    const msg = document.getElementById("profileMessage");
    const nextBio = String(bioInput?.value || "").trim();
    const payload = {
        profile_image_url: activeProfileImageUrl,
        bio: nextBio,
    };

    try {
        const response = await fetch(`${API_BASE_URL}/me/profile`, {
            method: "PATCH",
            headers: headers(),
            body: JSON.stringify(payload),
        });
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "Unable to save bio.");
        }

        activeBioText = String(result.data?.profile?.bio || nextBio || "").trim();
        activeProfileImageUrl = String(result.data?.profile?.profile_image_url || activeProfileImageUrl || "").trim();
        writeProfileCache({
            profile_image_url: activeProfileImageUrl,
            bio: activeBioText,
        });

        if (bioDisplay) {
            bioDisplay.textContent = activeBioText || DEFAULT_PROFILE_BIO;
        }
        if (msg) {
            msg.textContent = result.message || "Bio updated successfully.";
            msg.className = "form-message success";
        }

        if (result.data?.dashboard) {
            renderStats(result.data.dashboard.stats || []);
            renderActivities(result.data.dashboard.activities || []);
            const isStudent = String(result.data.profile?.role || "").toLowerCase() === "student";
            renderNotifications(result.data.dashboard.notifications || [], isStudent);
            renderActiveLoans(result.data.dashboard.active_loans || [], isStudent);
            renderUsers(result.data.management);
        }
    } catch (error) {
        activeBioText = nextBio;
        writeProfileCache({
            profile_image_url: activeProfileImageUrl,
            bio: activeBioText,
        });
        if (bioDisplay) {
            bioDisplay.textContent = activeBioText || DEFAULT_PROFILE_BIO;
        }
        if (msg) {
            msg.textContent = "Bio saved locally. Sync with server failed.";
            msg.className = "form-message error";
        }
    }

    setBioEditMode(false);
}

async function returnBookFromDashboard(button, { skipConfirm = false, skipReload = false } = {}) {
    const bookId = Number(button?.dataset?.bookId || 0);
    const transactionId = Number(button?.dataset?.transactionId || 0);
    if (!bookId || !transactionId) {
        return;
    }

    if (!skipConfirm) {
        const confirmed = await showConfirmPopup(
            "Are you sure you want to return this book?",
            "Return Book",
            "Return",
            "Cancel"
        );
        if (!confirmed) {
            return;
        }
    }

    if (button) {
        button.disabled = true;
    }
    const notificationMessage = document.getElementById("notificationsMessage");
    try {
        const response = await fetch(`${API_BASE_URL}/books/return`, {
            method: "POST",
            headers: headers(),
            cache: "no-store",
            body: JSON.stringify({
                book_id: bookId,
                transaction_id: transactionId,
            }),
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "Return failed.");
        }
        await showInfoPopup("Book returned successfully", "Success");
        const fine = Number(result.data?.fine_amount || 0);
        notificationMessage.textContent = fine > 0
            ? `Book returned. Fine pending: Rs. ${fine.toFixed(2)}.`
            : "Book returned successfully.";
        notificationMessage.className = `form-message ${fine > 0 ? "error" : "success"}`;
        if (!skipReload) {
            await loadDashboard();
        }
    } catch (error) {
        notificationMessage.textContent = error.message || "Unable to return book.";
        notificationMessage.className = "form-message error";
    } finally {
        if (button) {
            button.disabled = false;
        }
    }
}

async function checkDueBooksAndPrompt() {
    if (duePromptInProgress) {
        return;
    }
    duePromptInProgress = true;
    try {
        const response = await fetch(`${API_BASE_URL}/books/due-check`, {
            headers: headers(),
            cache: "no-store",
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            return;
        }

        const dueBooks = Array.isArray(result.data) ? result.data : [];
        if (!dueBooks.length) {
            return;
        }

        const dueBook = dueBooks[0];
        const shouldReturn = await showConfirmPopup(
            "Book is due. Please return it.",
            `Due Date: ${dueBook.due_date || "-"}`,
            "Return",
            "Cancel"
        );
        if (!shouldReturn) {
            return;
        }

        await returnBookFromDashboard(
            {
                dataset: {
                    bookId: String(dueBook.book_id || ""),
                    transactionId: String(dueBook.transaction_id || ""),
                },
            },
            { skipConfirm: true }
        );
    } catch (_error) {
        // Silent fallback to avoid blocking dashboard loading.
    } finally {
        duePromptInProgress = false;
    }
}

async function updateStatus(event) {
    const select = event.target.closest(".user-status");
    if (!select) {
        return;
    }
    const userId = select.dataset.id;
    const status = select.value;
    const response = await fetch(`${API_BASE_URL}/admin/users/${userId}/status`, {
        method: "PATCH",
        headers: headers(),
        body: JSON.stringify({ status }),
    });
    const result = await response.json();
    if (!response.ok || !result.success) {
        alert(result.message || "Unable to update.");
        await loadDashboard();
        return;
    }
    renderUsers(result.data.management);
}

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("editBioButton")?.addEventListener("click", beginBioEdit);
    document.getElementById("saveBioButton")?.addEventListener("click", saveBioInline);
    document.getElementById("cancelBioButton")?.addEventListener("click", cancelBioEdit);
    document.getElementById("usersBody").addEventListener("change", updateStatus);
    document.getElementById("dashboardAlertModal")?.addEventListener("click", (event) => {
        if (event.target.id === "dashboardAlertModal") {
            closeAlertModal();
        }
    });
    document.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action='return-book']");
        if (!button) {
            return;
        }
        await returnBookFromDashboard(button);
    });
    loadDashboard();
});
