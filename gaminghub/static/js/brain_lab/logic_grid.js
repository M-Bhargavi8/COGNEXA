(function () {

    const picker = document.getElementById("difficultyPicker");
    const gameArea = document.getElementById("gameArea");
    const cluesList = document.getElementById("cluesList");
    const answerRows = document.getElementById("answerRows");
    const hintBtn = document.getElementById("hintBtn");
    const submitBtn = document.getElementById("submitBtn");
    const resultArea = document.getElementById("resultArea");
    const resultHeading = document.getElementById("resultHeading");
    const resultDetails = document.getElementById("resultDetails");
    const bestBadge = document.getElementById("bestBadge");
    const playAgainBtn = document.getElementById("playAgainBtn");

    let players = [];
    let games = [];
    let phase = "idle";

    async function start(difficulty) {
        const res = await BrainLab.postJSON("/brain-lab/logic-grid/start", { difficulty });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        players = res.data.players;
        games = res.data.games;

        picker.style.display = "none";
        resultArea.style.display = "none";
        gameArea.style.display = "block";
        phase = "solving";
        hintBtn.disabled = false;
        hintBtn.textContent = "Use a Hint";

        cluesList.innerHTML = res.data.clues.map(c => `<li>${c}</li>`).join("");

        answerRows.innerHTML = players.map(p => `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <label class="text-light me-2" for="select-${p}">${p}</label>
                <select id="select-${p}" class="form-select w-auto" data-player="${p}">
                    <option value="">-- choose --</option>
                    ${games.map(g => `<option value="${g}">${g}</option>`).join("")}
                </select>
            </div>
        `).join("");
    }

    async function useHint() {
        if (phase !== "solving") return;

        const res = await BrainLab.postJSON("/brain-lab/logic-grid/hint", {});

        if (!res.success) {
            hintBtn.disabled = true;
            hintBtn.textContent = "No hints left";
            return;
        }

        const select = document.getElementById(`select-${res.data.player}`);
        if (select) select.value = res.data.game;

        const li = document.createElement("li");
        li.textContent = `Hint: ${res.data.player} plays ${res.data.game}.`;
        cluesList.appendChild(li);
    }

    async function submit() {
        if (phase !== "solving") return;
        phase = "submitting";

        const answers = {};
        players.forEach(p => {
            const select = document.getElementById(`select-${p}`);
            if (select && select.value) answers[p] = select.value;
        });

        const res = await BrainLab.postJSON("/brain-lab/logic-grid/submit", { answers });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        const d = res.data;

        gameArea.style.display = "none";
        resultArea.style.display = "block";

        resultHeading.textContent = d.correct_count === d.total ? "Solved it!":`${d.correct_count} / ${d.total} correct`;

        let details = `Accuracy ${d.accuracy}% · Score ${d.score} · +${d.xp} XP · +${d.coins} Coins`;
        if (d.hints_used > 0) {
            details += ` · ${d.hints_used} hint(s) used`;
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

    hintBtn.addEventListener("click", useHint);
    submitBtn.addEventListener("click", submit);

    playAgainBtn.addEventListener("click", () => {
        resultArea.style.display = "none";
        picker.style.display = "block";
    });

})();
