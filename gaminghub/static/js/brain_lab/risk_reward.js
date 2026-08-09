(function () {

    const picker = document.getElementById("difficultyPicker");
    const gameArea = document.getElementById("gameArea");
    const roundText = document.getElementById("roundText");
    const scoreDisplay = document.getElementById("scoreDisplay");
    const feedbackText = document.getElementById("feedbackText");
    const safeBtn = document.getElementById("safeBtn");
    const riskBtn = document.getElementById("riskBtn");
    const riskInfo = document.getElementById("riskInfo");
    const resultArea = document.getElementById("resultArea");
    const resultHeading = document.getElementById("resultHeading");
    const resultDetails = document.getElementById("resultDetails");
    const bestBadge = document.getElementById("bestBadge");
    const playAgainBtn = document.getElementById("playAgainBtn");

    let phase = "idle";
    let config = {};

    async function start(difficulty) {
        const res = await BrainLab.postJSON("/brain-lab/risk-reward/start", { difficulty });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        config = res.data;

        picker.style.display = "none";
        resultArea.style.display = "none";
        gameArea.style.display = "block";
        phase = "deciding";

        roundText.textContent = `Round 1 / ${config.rounds}`;
        scoreDisplay.textContent = "0";
        feedbackText.innerHTML = "&nbsp;";
        safeBtn.textContent = `SAFE (+${config.safe_gain})`;
        riskBtn.textContent = "RISK";
        riskInfo.textContent = `Potential +${config.risk_gain} · Potential -${config.risk_loss}`;
    }

    async function decide(choice) {
        if (phase !== "deciding") return;
        phase = "submitting";

        const res = await BrainLab.postJSON("/brain-lab/risk-reward/decide", { choice });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        const d = res.data;
        scoreDisplay.textContent = d.score;

        if (d.round_outcome === "safe") {
            feedbackText.textContent = `✅ Safe. +${config.safe_gain}`;
        } else if (d.round_outcome === "risk_win") {
            feedbackText.textContent = `🎉 Risk paid off! +${config.risk_gain}`;
        } else {
            feedbackText.textContent = `💥 Risk failed. -${config.risk_loss}`;
        }

        if (d.game_over) {
            showResult(d);
            return;
        }

        roundText.textContent = `Round ${d.round + 1} / ${d.rounds}`;
        phase = "deciding";
    }

    function showResult(d) {
        gameArea.style.display = "none";
        resultArea.style.display = "block";

        resultHeading.textContent = `Final Score: ${d.score}`;

        let details = `${d.decisions} decisions · ${d.risk_decisions} risky`;
        if (d.risk_success_rate !== null && d.risk_success_rate !== undefined) {
            details += ` (${d.risk_success_rate}% paid off)`;
        }
        details += ` · +${d.xp} XP · +${d.coins} Coins`;
        resultDetails.textContent = details;

        const badges = [];
        if (d.is_new_best) badges.push("🔥 NEW PERSONAL BEST");
        badges.push(BrainLab.formatExtras(d));
        bestBadge.textContent = badges.filter(Boolean).join(" · ");
    }

    document.querySelectorAll("[data-difficulty]").forEach(btn => {
        btn.addEventListener("click", () => start(btn.dataset.difficulty));
    });

    safeBtn.addEventListener("click", () => decide("safe"));
    riskBtn.addEventListener("click", () => decide("risk"));

    playAgainBtn.addEventListener("click", () => {
        resultArea.style.display = "none";
        picker.style.display = "block";
    });

})();
