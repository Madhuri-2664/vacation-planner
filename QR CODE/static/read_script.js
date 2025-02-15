document.addEventListener("DOMContentLoaded", function() {
    document.getElementById("read-form").addEventListener("submit", async function(event) {
        event.preventDefault();

        const fileInput = document.getElementById("qr-file");
        if (!fileInput.files.length) {
            return;
        }

        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        const token = localStorage.getItem("jwt_token");
        if (!token) {
            window.location.href = "/signin";
            return;
        }

        try {
            const response = await fetch("http://127.0.0.1:5000/read/qr", {
                method: "POST",
                headers: {
                    "Authorization": `${token}`  // Include the JWT token in the Authorization header
                },
                body: formData
            });

            if (response.ok) {
                const result = await response.json();
                document.getElementById("qr-data").innerHTML = `<p>QR Data: ${result.qr_data}</p>`;
            } else {
                const error = await response.json();
                document.getElementById("qr-data").innerHTML = `<p>Error: ${error.error}</p>`;
            }
        } catch (err) {
            console.error('Error during fetch:', err);
            document.getElementById("qr-data").innerHTML = `<p>Error: Unable to process the request.</p>`;
        }
    });
});
