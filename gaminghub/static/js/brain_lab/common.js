window.BrainLab = {

    csrfToken() {
        return document.querySelector('meta[name="csrf-token"]').content;
    },

    async postJSON(url, body) {
        const res = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": this.csrfToken()
            },
            body: JSON.stringify(body || {})
        });
        return res.json();
    },

    formatExtras(d) {
        const parts = [];
        (d.achievements_unlocked || []).forEach(a => parts.push(`🏆 ${a.badge || ""} ${a.title}`.trim()));
        if (d.challenge_completed) {
            parts.push(`🔥 Daily Challenge Complete! +${d.challenge_completed.xp} XP · +${d.challenge_completed.coins} Coins`);
        }
        return parts.join(" · ");
    }

};
