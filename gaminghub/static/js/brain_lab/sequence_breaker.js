(function () {

    const picker = document.getElementById("difficultyPicker");
    const gameArea = document.getElementById("gameArea");
    const sequenceDisplay = document.getElementById("sequenceDisplay");
    const answerInput = document.getElementById("answerInput");
    const submitBtn = document.getElementById("submitBtn");
    const resultArea = document.getElementById("resultArea");
    const resultHeading = document.getElementById("resultHeading");
    const resultDetails = document.getElementById("resultDetails");
    const bestBadge = document.getElementById("bestBadge");
    const playAgainBtn = document.getElementById("playAgainBtn");

    let phase = "idle";

    async function start(difficulty) {
        const res = await BrainLab.postJSON("/brain-lab/sequence-breaker/start", { difficulty });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        picker.style.display = "none";
        resultArea.style.display = "none";
        gameArea.style.display = "block";
        answerInput.value = "";
        phase = "answering";

        sequenceDisplay.textContent = res.data.sequence.join(" → ") + " → ? ";
        answerInput.focus();
    }

    async function submit() {
        if (phase !== "answering") return;
        phase = "submitting";

        const res = await BrainLab.postJSON("/brain-lab/sequence-breaker/submit", {
            answer: answerInput.value
        });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        const d = res.data;

        gameArea.style.display = "none";
        resultArea.style.display = "block";

        resultHeading.textContent = d.correct ? "Correct!" : `Not quite — it was ${d.correct_answer}`;

        let details = `Score ${d.score} · +${d.xp} XP · +${d.coins} Coins`;
        if (d.streak > 1) {
            details += ` · ${d.streak} in a row`;
        }
        resultDetails.textContent = details;

        const badges = [];
        if (d.is_new_best) badges.push("NEW PERSONAL BEST");
        badges.push(BrainLab.formatExtras(d));
        bestBadge.textContent = badges.filter(Boolean).join(" · ");
    }

    document.querySelectorAll("[data-difficulty]").forEach(btn => {
        btn.addEventListener("click", () => start(btn.dataset.difficulty));
    });

    submitBtn.addEventListener("click", submit);
    answerInput.addEventListener("keydown", e => {
        if (e.key === "Enter") submit();
    });

    playAgainBtn.addEventListener("click", () => {
        resultArea.style.display = "none";
        picker.style.display = "block";
    });

})();
