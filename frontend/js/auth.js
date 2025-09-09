const baseURL = "http://127.0.0.1:8000";

async function login() {
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    const formData = new FormData();
    formData.append("username", username);
    formData.append("password", password);

    const response = await fetch(`${baseURL}/login`, {
        method: "POST",
        body: formData,
    });

    const result = await response.json();
    if (response.ok && result.access_token) {
        localStorage.setItem("token", result.access_token);
        if (result.user_id) {
            localStorage.setItem("user_id", result.user_id);
        }
        window.location.href = "/static/upload.html"; 
    } else {
        alert(result.detail || "Login failed.");
    }
}

async function register() {
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    const formData = new FormData();
    formData.append("username", username);
    formData.append("password", password);

    const response = await fetch(`${baseURL}/register`, {
        method: "POST",
        body: formData,
    });

    const result = await response.json();
    if (response.ok) {
        alert("Registered successfully. Now log in.");
    } else {
        alert(result.detail || "Registration failed.");
    }
}
