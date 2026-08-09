(function () {

    const startPanel = document.getElementById("startPanel");
    const startBtn = document.getElementById("startBtn");
    const reflexBox = document.getElementById("reflexBox");
    const reflexText = document.getElementById("reflexText");
    const resultArea = document.getElementById("resultArea");
    const resultHeading = document.getElementById("resultHeading");
    const resultDetails = document.getElementById("resultDetails");
    const bestBadge = document.getElementById("bestBadge");
    const playAgainBtn = document.getElementById("playAgainBtn");

    let phase = "idle";
    let signalTime = 0;
    let timer = null;

    function csrfToken() {
        return document.querySelector('meta[name="csrf-token"]').content;
    }

    async function postJSON(url, body) {
        const res = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken()
            },
            body: JSON.stringify(body || {})
        });
        return res.json();
    }

    async function begin() {
        startPanel.style.display = "none";
        resultArea.style.display = "none";
        reflexBox.style.display = "flex";
        reflexBox.className = "reflex-box waiting mx-auto";
        reflexText.textContent = "WAIT...";
        phase = "waiting";

        const res = await postJSON("/brain-lab/reflex-lab/start", {});

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        timer = setTimeout(() => {
            phase = "ready";
            signalTime = performance.now();
            reflexBox.className = "reflex-box go mx-auto";
            reflexText.textContent = "CLICK!";
        }, res.data.delay_ms);
    }

    async function onBoxClick() {
        if (phase === "waiting") {
            clearTimeout(timer);
            phase = "idle";
            const res = await postJSON("/brain-lab/reflex-lab/submit", { early: true });
            showResult(res, true);
            return;
        }

        if (phase === "ready") {
            const reaction_ms = Math.round(performance.now() - signalTime);
            phase = "idle";
            const res = await postJSON("/brain-lab/reflex-lab/submit", { reaction_ms });
            showResult(res, false);
        }
    }

    function showResult(res, early) {
        reflexBox.style.display = "none";
        resultArea.style.display = "block";

        if (!res.success) {
            resultHeading.textContent = "Error";
            resultDetails.textContent = res.error.message;
            bestBadge.textContent = "";
            return;
        }

        const d = res.data;

        if (!d.valid) {
            resultHeading.textContent = early ? "⚡ Too soon!" : "Invalid attempt";
            resultDetails.textContent = early
                ? "You clicked before the signal appeared."
                : "That reaction time wasn't valid — try again.";
            bestBadge.textContent = "";
            return;
        }

        resultHeading.textContent = `${d.reaction_ms} ms`;

        let details = `Score ${d.score} · +${d.xp} XP · +${d.coins} Coins`;
        if (d.best_reaction_ms !== null && d.best_reaction_ms !== undefined) {
            details += ` · Best: ${d.best_reaction_ms} ms`;
        }
        resultDetails.textContent = details;

        bestBadge.textContent = d.is_new_best ? "🔥 NEW PERSONAL BEST" : "";
    }

    startBtn.addEventListener("click", begin);
    reflexBox.addEventListener("click", onBoxClick);

    playAgainBtn.addEventListener("click", () => {
        resultArea.style.display = "none";
        startPanel.style.display = "block";
    });

})();
