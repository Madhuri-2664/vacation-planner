// register_script.js
document.addEventListener("DOMContentLoaded", function() {
    document.getElementById("register-form").addEventListener("submit", async function(event) {
        event.preventDefault();

        const username = document.getElementById("username").value;
        const email = document.getElementById("email").value;
        const password = document.getElementById("password").value;

        const response = await fetch("http://127.0.0.1:5000/register", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ username: username, email: email, password: password })
        });

        if (response.ok) {
            // Successful registration
            const result = await response.json();
            alert(result.message || "Registration Successful");

            window.location.href = "/signin";
        } else {
            const error = await response.json();
            alert(error.error || "Something went wrong!");
        }
    });
});
