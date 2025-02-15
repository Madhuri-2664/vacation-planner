document.addEventListener("DOMContentLoaded", function() {
    document.getElementById("generate-form").addEventListener("submit", async function(event) {
        event.preventDefault();

        const content = document.getElementById("content").value;

        const token = localStorage.getItem("jwt_token");
        if (!token) {
            window.location.href = "/signin";
            return;
        }

        const response = await fetch("http://127.0.0.1:5000/generate/qr", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `${token}`  // Include the JWT token in the Authorization header
            },
            body: JSON.stringify({ content: content })
        });

        if (response.ok) {
            const blob = await response.blob();
            const imgUrl = URL.createObjectURL(blob);

            const qrImage = `<img src="${imgUrl}" alt="QR Code" />`;
            const downloadLink = `<a href="${imgUrl}" download="QRcode.png">Download QR Code</a>`;
            document.getElementById("generated-qr").innerHTML = qrImage + "<br>" + downloadLink;
        } else {
            const error = await response.json();
            alert(error.error || "Something went wrong!");
        }
    });
});
