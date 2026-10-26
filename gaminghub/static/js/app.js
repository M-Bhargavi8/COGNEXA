/*
 * Site-wide behaviour shared by every page (loaded from base.html and
 * the admin layout). Lives in a static file rather than inline <script>
 * so the Content-Security-Policy can forbid inline script entirely.
 */
(function () {
    "use strict";

    // Forms marked .cx-js-submit-once disable their submit button after
    // the first submit -- stops double-posts and shows a loading label.
    document.querySelectorAll("form.cx-js-submit-once").forEach(function (form) {
        form.addEventListener("submit", function () {
            var button = form.querySelector("button[type=submit]");
            if (!button || button.disabled) return;
            window.setTimeout(function () {
                button.disabled = true;
                button.setAttribute("aria-busy", "true");
                if (button.dataset.loadingText) button.textContent = button.dataset.loadingText;
            }, 0);
        });
    });

    // Submit buttons with data-confirm ask before their form is sent
    // (destructive admin actions). Capture phase on document, so this
    // runs before the submit-once handler can disable the button.
    document.addEventListener("submit", function (event) {
        var submitter = event.submitter;
        if (!submitter || !submitter.hasAttribute("data-confirm")) return;
        if (!window.confirm(submitter.dataset.confirm)) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);

    // Admin layout: off-canvas sidebar on small screens.
    var sidebar = document.getElementById("adminSidebar");
    var toggle = document.getElementById("adminSidebarToggle");
    var backdrop = document.getElementById("adminBackdrop");

    if (sidebar && toggle && backdrop) {
        toggle.addEventListener("click", function () {
            var isOpen = sidebar.classList.toggle("show");
            backdrop.classList.toggle("show", isOpen);
            toggle.setAttribute("aria-expanded", String(isOpen));
        });
        backdrop.addEventListener("click", function () {
            sidebar.classList.remove("show");
            backdrop.classList.remove("show");
            toggle.setAttribute("aria-expanded", "false");
        });
    }
})();
