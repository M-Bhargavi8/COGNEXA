(function () {

    const picker = document.getElementById("difficultyPicker");
    const gameArea = document.getElementById("gameArea");
    const statusText = document.getElementById("statusText");
    const guessInput = document.getElementById("guessInput");
    const guessBtn = document.getElementById("guessBtn");
    const history = document.getElementById("history");
    const resultArea = document.getElementById("resultArea");
    const resultHeading = document.getElementById("resultHeading");
    const resultDetails = document.getElementById("resultDetails");
    const bestBadge = document.getElementById("bestBadge");
    const playAgainBtn = document.getElementById("playAgainBtn");

    let digits = 0;
    let phase = "idle";

    function addHistoryRow(guessDigits, correctPosition, correctDigit) {
        const row = document.createElement("div");
        row.className = "d-flex justify-content-between border-bottom py-2";
        row.innerHTML = `
            <span>${guessDigits.join(" ")}</span>
            <span class="cx-pegs"><span class="cx-peg cx-peg--exact"></span>${correctPosition}<span class="cx-peg cx-peg--digit"></span>${correctDigit}</span>
        `;
        history.prepend(row);
    }

    async function start(difficulty) {
        const res = await BrainLab.postJSON("/brain-lab/code-breaker/start", { difficulty });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        digits = res.data.digits;

        picker.style.display = "none";
        resultArea.style.display = "none";
        gameArea.style.display = "block";
        history.innerHTML = "";
        guessInput.value = "";
        phase = "guessing";

        statusText.textContent = `Enter ${digits} unique digits (0-9). Attempts left: ${res.data.max_attempts}`;
        guessInput.setAttribute("maxlength", digits);
        guessInput.focus();
    }

    async function guess() {
        if (phase !== "guessing") return;

        const raw = guessInput.value.trim();

        if (raw.length !== digits || new Set(raw.split("")).size !== digits) {
            statusText.textContent = `Enter exactly ${digits} unique digits.`;
            return;
        }

        const guessDigits = raw.split("").map(Number);

        const res = await BrainLab.postJSON("/brain-lab/code-breaker/guess", {
            guess: guessDigits
        });

        if (!res.success) {
            alert(res.error.message);
            return;
        }

        const d = res.data;

        addHistoryRow(guessDigits, d.correct_position, d.correct_digit);
        guessInput.value = "";

        if (!d.game_over) {
            statusText.textContent = `Attempts left: ${d.attempts_left}`;
            return;
        }

        phase = "idle";
        gameArea.style.display = "none";
        resultArea.style.display = "block";

        if (d.won) {
            resultHeading.textContent = `Cracked it in ${d.attempts_used}!`;
        } else {
            resultHeading.textContent = `Out of attempts`;
        }

        resultDetails.textContent = d.won
            ? `Score ${d.score} · +${d.xp} XP · +${d.coins} Coins` : `The code was ${d.secret.join(" ")}`;

        const badges = [];
        if (d.is_new_best) badges.push("NEW PERSONAL BEST");
        badges.push(BrainLab.formatExtras(d));
        bestBadge.textContent = badges.filter(Boolean).join(" · ");
    }

    document.querySelectorAll("[data-difficulty]").forEach(btn => {
        btn.addEventListener("click", () => start(btn.dataset.difficulty));
    });

    guessBtn.addEventListener("click", guess);
    guessInput.addEventListener("keydown", e => {
        if (e.key === "Enter") guess();
    });

    playAgainBtn.addEventListener("click", () => {
        resultArea.style.display = "none";
        picker.style.display = "block";
    });

})();
