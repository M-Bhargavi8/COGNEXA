/* Analytics page charts. Data comes from the JSON block #analytics-data
   rendered by the server (not executed as script). */
(function () {
    "use strict";

    if (typeof Chart === "undefined") return;

    var dataEl = document.getElementById("analytics-data");
    if (!dataEl) return;

    var data = JSON.parse(dataEl.textContent);
    var shortLabels = data.labels.map(function (d) { return d.slice(5); });

    var gamesEl = document.getElementById("gamesChart");
    if (gamesEl) {
        new Chart(gamesEl, {
            type: "line",
            data: {
                labels: shortLabels,
                datasets: [{
                    label: "Games Played",
                    data: data.games_played,
                    borderColor: "#34D399",
                    backgroundColor: "rgba(52, 211, 153, 0.15)",
                    tension: 0.25,
                    fill: true
                }]
            },
            options: {
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                plugins: { legend: { display: false } }
            }
        });
    }

    var xpEl = document.getElementById("xpChart");
    if (xpEl) {
        new Chart(xpEl, {
            type: "line",
            data: {
                labels: shortLabels,
                datasets: [{
                    label: "XP Earned",
                    data: data.xp_earned,
                    borderColor: "#FBBF24",
                    backgroundColor: "rgba(251, 191, 36, 0.15)",
                    tension: 0.25,
                    fill: true
                }]
            },
            options: {
                scales: { y: { beginAtZero: true } },
                plugins: { legend: { display: false } }
            }
        });
    }

    var skillEl = document.getElementById("skillChart");
    if (skillEl) {
        var skillProfile = data.skill_profile;
        new Chart(skillEl, {
            type: "bar",
            data: {
                labels: skillProfile.map(function (s) { return s.skill; }),
                datasets: [{
                    label: "Win Rate",
                    data: skillProfile.map(function (s) { return s.score; }),
                    backgroundColor: "#5B8CFF"
                }]
            },
            options: {
                indexAxis: "y",
                scales: { x: { beginAtZero: true, max: 100 } },
                plugins: { legend: { display: false } }
            }
        });
    }
})();
