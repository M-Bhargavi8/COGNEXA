(function () {

    const picker = document.getElementById("difficultyPicker");
    const gameArea = document.getElementById("gameArea");
    const grid = document.getElementById("grid");
    const statusText = document.getElementById("statusText");
    const submitBtn = document.getElementById("submitBtn");
    const resultArea = document.getElementById("resultArea");
    const resultHeading = document.getElementById("resultHeading");
    const resultDetails = document.getElementById("resultDetails");
    const bestBadge = document.getElementById("bestBadge");
    const playAgainBtn = document.getElementById("playAgainBtn");

    let selected = new Set();
    let phase = "idle";

    function csrfToken() {
        return document.querySelector('meta[name="csrf-token"]').content;
    }

    async function postJSON(url, body) {
        const res = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type" : "application/json",
                "X-CSRFToken": csrfToken()
            },
            body: JSON.stringify(body || {})
        });
        return res.json();
    }

    function cellEls() {
        return Array.from(grid.querySelectorAll(".memory-cell"));
    }

    function buildGrid(n) {
        grid.innerHTML = "";
        grid.style.gridTemplateColumns = `repeat(${n}, 1fr)`;

        for (let i = 0; i < n * n; i++) {
            const cell = document.createElement("div");
            cell.className = "memory-cell";
            cell.dataset.index = i;
            cell.addEventListener("click", () => onCellClick(cell));
            grid.appendChild(cell);
        }
    }

    function onCellClick(cell) {
        if (phase !== "recall") return;

        const idx = Number(cell.dataset.index);

        if (selected.has(idx)) {
            selected.delete(idx);
            cell.classList.remove("selected");
        } else {
            selected.add(idx);
            cell.classList.add("selected");
        }
    }

    async function start(difficulty) {
        const res = await postJSON("/brain-lab/memory-matrix/start", { difficulty });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        const { pattern, grid: n, reveal_ms } = res.data;

        picker.style.display = "none";
        resultArea.style.display = "none";
        gameArea.style.display = "block";
        submitBtn.style.display = "none";
        selected = new Set();
        phase = "reveal";

        statusText.textContent = "Memorize the pattern...";

        buildGrid(n);
        const cells = cellEls();
        pattern.forEach(i => cells[i].classList.add("lit"));

        setTimeout(() => {
            cells.forEach(c => c.classList.remove("lit"));
            statusText.textContent = "Click the cells you remember, then Submit.";
            phase = "recall";
            submitBtn.style.display = "inline-block";
        }, reveal_ms);
    }

    async function submit() {
        if (phase !== "recall") return;
        phase = "submitting";

        const res = await postJSON("/brain-lab/memory-matrix/submit", {
            selected: Array.from(selected)
        });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        const d = res.data;

        gameArea.style.display = "none";
        resultArea.style.display = "block";

        resultHeading.textContent = d.accuracy >= 50 ? "Well done!" : "Keep practicing";

        let details = `Accuracy ${d.accuracy}% · Score ${d.score} · +${d.xp} XP · +${d.coins} Coins`;
        if (d.streak > 1) {
            details += ` · ${d.streak} in a row`;
        }
        resultDetails.textContent = details;

        const badges = [];
        if (d.is_new_best) badges.push("NEW PERSONAL BEST");
        (d.achievements_unlocked || []).forEach(a => badges.push(`${a.title}`));
        if (d.challenge_completed) badges.push(`Daily Challenge Complete! +${d.challenge_completed.xp} XP · +${d.challenge_completed.coins} Coins`);
        bestBadge.textContent = badges.join(" · ");
    }

    document.querySelectorAll("[data-difficulty]").forEach(btn => {
        btn.addEventListener("click", () => start(btn.dataset.difficulty));
    });

    submitBtn.addEventListener("click", submit);

    playAgainBtn.addEventListener("click", () => {
        resultArea.style.display = "none";
        picker.style.display = "block";
    });

})();
