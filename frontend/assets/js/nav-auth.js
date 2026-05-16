(function () {
    const themeKey = "smartLibraryTheme";
    const root = document.documentElement;
    const savedTheme = localStorage.getItem(themeKey);
    if (savedTheme === "dark" || savedTheme === "light") {
        root.setAttribute("data-theme", savedTheme);
    } else {
        root.setAttribute("data-theme", "light");
    }

    function toggleTheme() {
        const current = root.getAttribute("data-theme") || "light";
        const next = current === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        localStorage.setItem(themeKey, next);
    }

    const nav = document.querySelector(".navbar");
    if (!nav) {
        return;
    }

    const token = localStorage.getItem("smartLibraryToken");
    const user = JSON.parse(localStorage.getItem("smartLibraryUser") || "null");
    const isLoggedIn = Boolean(token && user);

    const links = [
        { label: "Home", href: "../index.html", rootHref: "index.html" },
        { label: "Books", href: "books.html", rootHref: "pages/books.html" },
        { label: "AI", href: "ai-features.html", rootHref: "pages/ai-features.html" },
        { label: "Dashboard", href: "dashboard.html", rootHref: "pages/dashboard.html" },
    ];

    const onRoot = !window.location.pathname.toLowerCase().includes("/pages/");
    const activePath = window.location.pathname.toLowerCase();

    const navInner = document.createElement("div");
    navInner.className = "nav-inner";

    const brand = document.createElement("a");
    brand.className = "brand";
    brand.href = onRoot ? "index.html" : "../index.html";
    brand.innerHTML = '<span class="brand-badge">SL</span><span>Smart Library</span>';

    const navLinks = document.createElement("ul");
    navLinks.className = "nav-links";
    links.forEach((item) => {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.textContent = item.label;
        a.href = onRoot ? item.rootHref : item.href;
        if (activePath.endsWith((onRoot ? item.rootHref : item.href).toLowerCase()) || (item.label === "Home" && (activePath.endsWith("/frontend/") || activePath.endsWith("index.html")))) {
            a.classList.add("active-link");
        }
        li.appendChild(a);
        navLinks.appendChild(li);
    });

    const navRight = document.createElement("div");
    navRight.className = "nav-right";

    const themeBtn = document.createElement("button");
    themeBtn.className = "theme-toggle";
    themeBtn.type = "button";
    themeBtn.textContent = "Theme";
    themeBtn.addEventListener("click", toggleTheme);
    navRight.appendChild(themeBtn);

    if (isLoggedIn) {
        const avatarMenu = document.createElement("div");
        avatarMenu.className = "avatar-menu";

        const avatarBtn = document.createElement("button");
        avatarBtn.className = "avatar-btn";
        avatarBtn.type = "button";
        const initials = String(user.full_name || "U")
            .split(" ")
            .slice(0, 2)
            .map((x) => x[0]?.toUpperCase() || "")
            .join("") || "U";
        avatarBtn.textContent = initials;

        const dropdown = document.createElement("div");
        dropdown.className = "avatar-dropdown";

        const profile = document.createElement("a");
        profile.href = onRoot ? "pages/dashboard.html" : "dashboard.html";
        profile.textContent = "Profile";

        const logout = document.createElement("button");
        logout.type = "button";
        logout.textContent = "Logout";
        logout.addEventListener("click", () => {
            localStorage.removeItem("smartLibraryToken");
            localStorage.removeItem("smartLibraryUser");
            localStorage.removeItem("smartLibraryAiChatHistory");
            window.location.href = onRoot ? "pages/login.html" : "login.html";
        });

        dropdown.appendChild(profile);
        dropdown.appendChild(logout);

        avatarBtn.addEventListener("click", () => {
            dropdown.classList.toggle("open");
        });
        document.addEventListener("click", (event) => {
            if (!avatarMenu.contains(event.target)) {
                dropdown.classList.remove("open");
            }
        });

        avatarMenu.appendChild(avatarBtn);
        avatarMenu.appendChild(dropdown);
        navRight.appendChild(avatarMenu);
    } else {
        const loginBtn = document.createElement("a");
        loginBtn.textContent = "Login";
        loginBtn.href = onRoot ? "pages/login.html" : "login.html";
        loginBtn.className = "btn btn-primary";
        navRight.appendChild(loginBtn);
    }

    navInner.appendChild(brand);
    navInner.appendChild(navLinks);
    navInner.appendChild(navRight);

    nav.innerHTML = "";
    nav.appendChild(navInner);
})();
