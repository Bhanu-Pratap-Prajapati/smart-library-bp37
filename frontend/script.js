const API_BOOKS = "https://smart-library-backend-ngj7.onrender.com/api/books";
const currentUser = JSON.parse(localStorage.getItem("smartLibraryUser") || "null");

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function cardTemplate(book) {
    return window.SmartLibraryBookCard.renderBookCard(book, {
        user: currentUser,
        showDelete: false,
        showBookId: false,
        contentClass: "media-content",
        contentStyle: "",
        fallbackImage: "https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?auto=format&fit=crop&w=800&q=80",
    });
}

function renderSection(id, books, fallback = "No items") {
    const node = document.getElementById(id);
    if (!node) {
        return;
    }
    if (!books.length) {
        node.innerHTML = `<p class="small">${fallback}</p>`;
        return;
    }
    node.innerHTML = `<div class="grid grid-auto">${books.map(cardTemplate).join("")}</div>`;
}

async function initHome() {
    const status = document.getElementById("homeStatus");
    try {
        const response = await fetch(API_BOOKS);
        const result = await response.json();
        const books = response.ok && result.success ? (result.data || []) : [];

        const featured = books.slice(0, 8);
        renderSection("featuredBooks", featured);

        const recResponse = await fetch(`${API_BOOKS}/recommendations`);
        const recResult = await recResponse.json();
        const recommended = recResponse.ok && recResult.success ? (recResult.data || []).slice(0, 8) : books.slice(8, 16);
        renderSection("recommendedBooks", recommended);

        const categories = Array.from(new Set(books.map((b) => (b.category || "General").split(",")[0].trim()).filter(Boolean))).slice(0, 8);
        const catNode = document.getElementById("categories");
        catNode.innerHTML = categories.map((cat) => `<button class="btn btn-secondary category-pill" type="button" data-cat="${escapeHtml(cat)}">${escapeHtml(cat)}</button>`).join("");

        status.textContent = "Ready";
    } catch {
        status.textContent = "Backend offline";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initHome();

    document.getElementById("goBooksBtn")?.addEventListener("click", () => {
        window.location.href = "pages/books.html";
    });

    document.getElementById("globalSearchForm")?.addEventListener("submit", (event) => {
        event.preventDefault();
        const q = document.getElementById("globalSearchInput").value.trim();
        if (!q) {
            return;
        }
        window.location.href = `pages/books.html?q=${encodeURIComponent(q)}`;
    });

    document.getElementById("categories")?.addEventListener("click", (event) => {
        const target = event.target.closest("button[data-cat]");
        if (!target) {
            return;
        }
        const q = target.dataset.cat || "";
        window.location.href = `pages/books.html?q=${encodeURIComponent(q)}`;
    });

    const handleIssueClick = (event) => {
        const button = event.target.closest("button[data-action='issue']");
        if (!button) {
            return;
        }
        const q = button.dataset.bookId || button.dataset.title || "";
        window.location.href = `pages/books.html?q=${encodeURIComponent(q)}`;
    };

    document.getElementById("featuredBooks")?.addEventListener("click", handleIssueClick);
    document.getElementById("recommendedBooks")?.addEventListener("click", handleIssueClick);
});
