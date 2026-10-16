(function () {

    const picker = document.getElementById("difficultyPicker");
    const sequencePhase = document.getElementById("sequencePhase");
    const sequenceDisplay = document.getElementById("sequenceDisplay");
    const mathPhase = document.getElementById("mathPhase");
    const mathProblem = document.getElementById("mathProblem");
    const mathInput = document.getElementById("mathInput");
    const mathSubmitBtn = document.getElementById("mathSubmitBtn");
    const recallPhase = document.getElementById("recallPhase");
    const recallInput = document.getElementById("recallInput");
    const recallSubmitBtn = document.getElementById("recallSubmitBtn");
    const resultArea = document.getElementById("resultArea");
    const resultHeading = document.getElementById("resultHeading");
    const resultDetails = document.getElementById("resultDetails");
    const bestBadge = document.getElementById("bestBadge");
    const playAgainBtn = document.getElementById("playAgainBtn");

    let phase = "idle";
    let mathAnswer = "";

    function hideAll() {
        picker.style.display = "none";
        sequencePhase.style.display = "none";
        mathPhase.style.display = "none";
        recallPhase.style.display = "none";
        resultArea.style.display = "none";
    }

    async function start(difficulty) {
        const res = await BrainLab.postJSON("/brain-lab/dual-task/start", { difficulty });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        const d = res.data;

        hideAll();
        sequencePhase.style.display = "block";
        sequenceDisplay.textContent = d.sequence.join(" → ");
        phase = "sequence";

        setTimeout(() => {
            hideAll();
            mathPhase.style.display = "block";
            mathProblem.textContent = d.math_problem + " = ? ";
            mathInput.value = "";
            phase = "math";
            mathInput.focus();
        }, d.reveal_ms);
    }

    function goToRecall() {
        if (phase !== "math") return;

        mathAnswer = mathInput.value;

        hideAll();
        recallPhase.style.display = "block";
        recallInput.value = "";
        phase = "recall";
        recallInput.focus();
    }

    async function submitRecall() {
        if (phase !== "recall") return;
        phase = "submitting";

        const sequenceRecall = recallInput.value
            .trim()
            .split(/[\s,]+/)
            .filter(s => s !== "")
            .map(Number);

        const res = await BrainLab.postJSON("/brain-lab/dual-task/submit", {
            math_answer: mathAnswer,
            sequence_recall: sequenceRecall
        });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        const d = res.data;

        hideAll();
        resultArea.style.display = "block";

        resultHeading.textContent = d.overall >= 50 ? "Nice multitasking!" : "Keep practicing";

        resultDetails.textContent =
            `Math ${d.math_correct ? "correct" : "wrong (" + d.math_answer + ")"} · ` +
            `Memory ${d.memory_accuracy}% · Overall ${d.overall}% · ` +
            `Score ${d.score} · +${d.xp} XP · +${d.coins} Coins`;

        const badges = [];
        if (d.is_new_best) badges.push("NEW PERSONAL BEST");
        badges.push(BrainLab.formatExtras(d));
        bestBadge.textContent = badges.filter(Boolean).join(" · ");
    }

    document.querySelectorAll("[data-difficulty]").forEach(btn => {
        btn.addEventListener("click", () => start(btn.dataset.difficulty));
    });

    mathSubmitBtn.addEventListener("click", goToRecall);
    mathInput.addEventListener("keydown", e => { if (e.key === "Enter") goToRecall(); });

    recallSubmitBtn.addEventListener("click", submitRecall);
    recallInput.addEventListener("keydown", e => { if (e.key === "Enter") submitRecall(); });

    playAgainBtn.addEventListener("click", () => {
        hideAll();
        picker.style.display = "block";
    });

})();
