(() => {
    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function escapeRegex(value) {
        return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }

    function highlightText(text, query) {
        const safeText = String(text || "");
        const safeQuery = String(query || "").trim();
        if (!safeQuery) {
            return escapeHtml(safeText);
        }
        const pattern = new RegExp(`(${escapeRegex(safeQuery)})`, "ig");
        const parts = safeText.split(pattern);
        const queryLower = safeQuery.toLowerCase();
        return parts
            .map((part) => (part.toLowerCase() === queryLower ? `<mark class="search-highlight">${escapeHtml(part)}</mark>` : escapeHtml(part)))
            .join("");
    }

    function renderBookCard(book, options = {}) {
        const {
            user = null,
            isAdminLike = false,
            showDelete = false,
            showBookId = true,
            highlightQuery = "",
            contentClass = "media-content grid",
            contentStyle = " style=\"gap:8px;\"",
            fallbackImage = "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=700&q=70",
        } = options;

        const available = Number(book.available_copies || 0);
        const canIssue = available > 0;
        const img = book.thumbnail_url || book.cover_url || fallbackImage;
        const authorLine = showBookId
            ? `${highlightText(book.author_name, highlightQuery)} | ID: ${highlightText(book.id, highlightQuery)}`
            : `${highlightText(book.author_name, highlightQuery)}`;

        return `
            <article class="media-card">
                <img class="media-thumb" src="${escapeHtml(img)}" alt="${escapeHtml(book.title)}">
                <div class="${contentClass}"${contentStyle}>
                    <strong>${highlightText(book.title, highlightQuery)}</strong>
                    <p class="small">${authorLine}</p>
                    <span class="badge ${available > 0 ? "ok" : "warn"}">${available > 0 ? "Available" : "Issued"}</span>
                    <div class="actions">
                        <button class="btn btn-primary" type="button" data-action="issue" data-book-id="${book.id}" data-title="${escapeHtml(book.title)}" ${canIssue ? "" : "disabled"}>Issue</button>
                        ${(showDelete && isAdminLike) ? `<button class="btn btn-danger" type="button" data-action="delete" data-book-id="${book.id}">Delete</button>` : ""}
                    </div>
                </div>
            </article>
        `;
    }

    window.SmartLibraryBookCard = {
        escapeHtml,
        renderBookCard,
    };
})();
