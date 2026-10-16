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
    let changedValues = [];

    function cellEls() {
        return Array.from(grid.querySelectorAll(".memory-cell"));
    }

    function buildGrid(values) {
        grid.innerHTML = "";
        const cols = Math.ceil(Math.sqrt(values.length));
        grid.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;

        values.forEach((value, i) => {
            const cell = document.createElement("div");
            cell.className = "memory-cell focus-cell";
            cell.dataset.index = i;
            // The swatch is a CSS dot keyed off data-color rather than a
            // text glyph, so every cell is the same size and shape.
            cell.dataset.color = value;
            cell.setAttribute("aria-label", value);
            cell.innerHTML = '<span class="focus-dot"></span>';
            cell.addEventListener("click", () => onCellClick(cell));
            grid.appendChild(cell);
        });
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
        const res = await BrainLab.postJSON("/brain-lab/focus-shift/start", { difficulty });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        const { original, changed, reveal_ms } = res.data;
        changedValues = changed;

        picker.style.display = "none";
        resultArea.style.display = "none";
        gameArea.style.display = "block";
        submitBtn.style.display = "none";
        selected = new Set();
        phase = "reveal";

        statusText.textContent = "Study the grid...";
        buildGrid(original);

        setTimeout(() => {
            buildGrid(changedValues);
            statusText.textContent = "Click what changed, then Submit.";
            phase = "recall";
            submitBtn.style.display = "inline-block";
        }, reveal_ms);
    }

    async function submit() {
        if (phase !== "recall") return;
        phase = "submitting";

        const res = await BrainLab.postJSON("/brain-lab/focus-shift/submit", {
            selected: Array.from(selected)
        });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        const d = res.data;

        gameArea.style.display = "none";
        resultArea.style.display = "block";

        resultHeading.textContent = d.accuracy >= 50 ? "Sharp eyes!" : "Keep practicing";

        let details = `Accuracy ${d.accuracy}% · Score ${d.score} · +${d.xp} XP · +${d.coins} Coins`;
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

    playAgainBtn.addEventListener("click", () => {
        resultArea.style.display = "none";
        picker.style.display = "block";
    });

})();
