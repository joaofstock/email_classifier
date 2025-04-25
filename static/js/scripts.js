document.addEventListener("DOMContentLoaded", function () {
    updateDashboard();  // Run immediately
    setInterval(updateDashboard, 10000); // Auto-refresh every 10 seconds
});

function updateDashboard() {
    fetchSentimentData();
    fetchTagData();
    fetchEmails();
}

function fetchSentimentData() {
    fetch("/api/sentiment")
        .then(response => response.json())
        .then(data => {
            const labels = Object.keys(data);
            const values = Object.values(data);
            renderChart("sentimentChart", "Sentiment Analysis", labels, values);
        })
        .catch(error => console.error("Error fetching sentiment data:", error));
}

function fetchTagData() {
    fetch("/api/tags")
        .then(response => response.json())
        .then(data => {
            const labels = Object.keys(data);
            const values = Object.values(data);
            renderChart("tagChart", "Emails per Tag", labels, values);
        })
        .catch(error => console.error("Error fetching tag data:", error));
}

function fetchEmails() {
    fetch("/api/emails")
        .then(response => response.json())
        .then(data => {
            const tableBody = document.getElementById("emailTableBody");
            tableBody.innerHTML = "";
            data.forEach(email => {
                const row = `<tr>
                    <td>${email.sender}</td>
                    <td>${email.subject}</td>
                    <td>${email.tag}</td>
                    <td>${email.sentiment}</td>
                    <td>${email.summary}</td>
                </tr>`;
                tableBody.innerHTML += row;
            });
        })
        .catch(error => console.error("Error fetching emails:", error));
}

function renderChart(canvasId, title, labels, data) {
    const ctx = document.getElementById(canvasId).getContext("2d");
    new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [{
                label: title,
                data: data,
                backgroundColor: ["#FF5733", "#33FF57", "#3357FF", "#FFD700", "#FF33A8"],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}
