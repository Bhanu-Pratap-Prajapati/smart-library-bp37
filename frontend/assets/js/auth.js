const API_BASE_URL = "https://smart-library-backend-ngj7.onrender.com/api";

function showMessage(elementId, message, type = "") {
    const el = document.getElementById(elementId);
    if (!el) {
        return;
    }
    el.textContent = message;
    el.className = `form-message ${type}`.trim();
}

async function loginUser(email, password) {
    const response = await fetch(`${API_BASE_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
    });
    const result = await response.json();
    if (!response.ok || !result.success) {
        throw new Error(result.message || "Login failed.");
    }
    localStorage.setItem("smartLibraryUser", JSON.stringify(result.user));
    localStorage.setItem("smartLibraryToken", result.token);
    return result;
}

async function handleLogin(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form).entries());
    try {
        await loginUser(payload.email, payload.password);
        showMessage("loginMessage", "Login successful.", "success");
        setTimeout(() => {
            window.location.href = "../index.html";
        }, 300);
    } catch (error) {
        showMessage("loginMessage", error.message, "error");
    }
}

async function handleRegister(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form).entries());

    if ((payload.password || "") !== (payload.confirm_password || "")) {
        showMessage("registerMessage", "Password and confirm password must match.", "error");
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                full_name: payload.full_name,
                email: payload.email,
                password: payload.password,
                role: payload.role || "student",
            }),
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "Registration failed.");
        }

        await loginUser(payload.email, payload.password);
        showMessage("registerMessage", "Account created.", "success");
        setTimeout(() => {
            window.location.href = "../index.html";
        }, 300);
    } catch (error) {
        showMessage("registerMessage", error.message, "error");
    }
}

function setupRoleCards() {
    const cards = document.querySelectorAll("#registerRoleSelector .role-card");
    const input = document.getElementById("registerRole");
    if (!cards.length || !input) {
        return;
    }

    cards.forEach((card) => {
        card.addEventListener("click", () => {
            cards.forEach((c) => c.classList.remove("active"));
            card.classList.add("active");
            input.value = card.dataset.role;
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("loginForm")?.addEventListener("submit", handleLogin);
    document.getElementById("registerForm")?.addEventListener("submit", handleRegister);
    setupRoleCards();
});
