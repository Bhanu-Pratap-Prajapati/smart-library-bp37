const API_URL = "http://127.0.0.1:5000/api/ai/chat";
const API_HISTORY_URL = "http://127.0.0.1:5000/api/ai/history";
const HISTORY_KEY = "smartLibraryAiChatHistory";

const state = {
    messages: [],
    history: [],
};

function esc(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function getToken() {
    return localStorage.getItem("smartLibraryToken") || "";
}

async function loadHistoryFromServer() {
    const token = getToken();
    if (!token) {
        state.history = [];
        renderHistory();
        return;
    }

    try {
        const response = await fetch(API_HISTORY_URL, {
            method: "GET",
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "Unable to load chat history.");
        }

        const entries = Array.isArray(result.data) ? result.data : [];
        state.history = entries
            .filter((item) => String(item.role || "").toLowerCase() === "user")
            .map((item) => ({
                query: item.message,
                ts: item.timestamp ? new Date(item.timestamp).getTime() : Date.now(),
            }))
            .slice(-20)
            .reverse();
        renderHistory();
    } catch {
        state.history = [];
        renderHistory();
    }
}

function setStatus(message) {
    const status = document.getElementById("aiStatusText");
    if (status) {
        status.textContent = message;
    }
}

function renderHistory() {
    const list = document.getElementById("aiHistoryList");
    if (!list) {
        return;
    }

    if (!state.history.length) {
        list.innerHTML = '<li class="small" style="color:var(--text-muted);">No previous chats</li>';
        return;
    }

    list.innerHTML = state.history
        .map((entry) => `
            <li>
                <button type="button" class="ai-history-item" data-history-prompt="${esc(entry.query)}">${esc(entry.query)}</button>
            </li>
        `)
        .join("");
}

function addMessage(role, text, payload = null) {
    state.messages.push({ role, text, payload });
    renderMessages();
}

function renderStructuredResponse(payload) {
    if (!payload || typeof payload !== "object") {
        return "";
    }

    const books = Array.isArray(payload.books) ? payload.books : [];
    const issued = Array.isArray(payload.issued_books) ? payload.issued_books : [];
    const fines = Array.isArray(payload.fines) ? payload.fines : [];
    let html = "";

    if (books.length) {
        html += `<div class="ai-book-list">${books.slice(0, 6).map((book) => `
            <article class="ai-mini-card">
                <strong>${esc(book.title)}</strong>
                <span class="small">${esc(book.author_name)}${book.category ? ` | ${esc(book.category)}` : ""}</span>
            </article>
        `).join("")}</div>`;
    }

    if (issued.length) {
        html += `<div class="ai-book-list">${issued.slice(0, 6).map((item) => `
            <article class="ai-mini-card">
                <strong>${esc(item.title)}</strong>
                <span class="small">Due: ${esc(item.due_at || "-")} | Status: ${esc(item.status || "-")}</span>
            </article>
        `).join("")}</div>`;
    }

    if (fines.length) {
        html += `<div class="ai-fine-list">${fines.slice(0, 6).map((item) => `
            <article class="ai-mini-card">
                <strong>Transaction #${esc(item.transaction_id)}</strong>
                <span class="small">Fine: ${esc(item.fine_amount)}</span>
            </article>
        `).join("")}</div>`;
    }

    return html;
}

function renderMessages() {
    const wrapper = document.getElementById("aiMessages");
    if (!wrapper) {
        return;
    }

    if (!state.messages.length) {
        wrapper.innerHTML = `
            <div class="ai-row ai-row-assistant">
                <div class="ai-bubble ai-bubble-assistant">
                    Hello. Ask about books, recommendations, issued books, or fine details.
                </div>
            </div>
        `;
        return;
    }

    wrapper.innerHTML = state.messages
        .map((item) => `
            <div class="ai-row ${item.role === "user" ? "ai-row-user" : "ai-row-assistant"}">
                <div class="ai-bubble ${item.role === "user" ? "ai-bubble-user" : "ai-bubble-assistant"}">
                    ${esc(item.text)}${item.role === "assistant" ? renderStructuredResponse(item.payload) : ""}
                </div>
            </div>
        `)
        .join("");

    requestAnimationFrame(() => {
        wrapper.scrollTo({
            top: wrapper.scrollHeight,
            behavior: "smooth",
        });
    });
}

function startNewChat() {
    state.messages = [];
    renderMessages();
    setStatus("New chat started.");
}

async function requestAssistant(query) {
    const headers = { "Content-Type": "application/json" };
    const token = getToken();
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(API_URL, {
        method: "POST",
        headers,
        body: JSON.stringify({ query }),
    });

    const result = await response.json();
    if (!response.ok || !result.success) {
        throw new Error(result.message || "Unable to process request.");
    }
    return result.data || {};
}

async function submitQuery(queryText) {
    const query = String(queryText || "").trim();
    if (!query) {
        return;
    }

    addMessage("user", query);
    setStatus("Thinking...");

    try {
        const payload = await requestAssistant(query);
        const answer = payload.answer || "I could not generate a response.";
        addMessage("assistant", answer, payload);
        await loadHistoryFromServer();
        setStatus("Response ready.");
    } catch (error) {
        addMessage("assistant", error.message || "Something went wrong.");
        setStatus("Failed to process request.");
    }
}

function bindSidebarActions() {
    document.addEventListener("click", (event) => {
        const historyBtn = event.target.closest("[data-history-prompt]");
        if (historyBtn) {
            submitQuery(historyBtn.getAttribute("data-history-prompt") || "");
            return;
        }

        const chip = event.target.closest("[data-ai-prompt]");
        if (chip) {
            submitQuery(chip.getAttribute("data-ai-prompt") || "");
        }
    });
}

function bindForm() {
    const form = document.getElementById("aiChatForm");
    const input = document.getElementById("aiChatInput");
    if (!form || !input) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const value = input.value;
        input.value = "";
        await submitQuery(value);
        input.focus();
    });

    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            form.requestSubmit();
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    localStorage.removeItem(HISTORY_KEY);
    loadHistoryFromServer();
    renderMessages();
    bindForm();
    bindSidebarActions();
    document.getElementById("aiNewChatBtn")?.addEventListener("click", startNewChat);
});
