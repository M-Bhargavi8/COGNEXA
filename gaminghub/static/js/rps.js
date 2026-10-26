/* Rock Paper Scissors reveal countdown. The round's result comes from
   the server via data-result on #battle (Win / Lose / Draw). */
(function () {
    "use strict";

    var countdown = document.getElementById("countdown");
    var battle = document.getElementById("battle");

    if (!countdown || !battle) return;

    var result = battle.dataset.result;
    var number = 3;

    countdown.textContent = number;

    var timer = setInterval(function () {
        number--;

        if (number > 0) {
            countdown.textContent = number;
        } else if (number === 0) {
            countdown.textContent = "GO!";
        } else {
            clearInterval(timer);
            countdown.style.display = "none";
            battle.style.display = "block";

            if (result === "Win") {
                document.getElementById("winSound").play();
                showReward(20, 15);
            } else if (result === "Lose") {
                document.getElementById("loseSound").play();
            }
        }
    }, 1000);
})();
