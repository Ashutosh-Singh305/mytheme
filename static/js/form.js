document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector("#user-reg-form");
    if (!form) return;

    /**
     * Switches to the tab containing the error field, focuses, and scrolls to it.
     * @param {HTMLElement} field - The invalid form element.
     */
    function openErrorTab(field) {
        if (!field) return;

        const pane = field.closest(".tab-pane");
        if (!pane) return;

        // Find the matching Bootstrap tab trigger link/button
        const tabButton = document.querySelector(`[data-bs-target="#${pane.id}"], [href="#${pane.id}"]`);
        if (!tabButton) return;

        // Activate the Bootstrap tab
        bootstrap.Tab.getOrCreateInstance(tabButton).show();

        // Smoothly focus and center the field after the tab animation completes
        setTimeout(() => {
            field.focus();
            field.scrollIntoView({
                behavior: "smooth",
                block: "center"
            });
        }, 200);
    }

    /**
     * Scans tabs in sequential order to find the very first field with a Django validation error.
     * @returns {HTMLElement|null} The first invalid field found, or null.
     */
    function getFirstErrorField() {
        const tabOrder = ["general", "personal", "profile", "permissions", "dates"];

        for (const tabId of tabOrder) {
            const pane = document.getElementById(tabId);
            if (!pane) continue;

            // Django individual field errors render inside .text-danger elements
            const error = pane.querySelector(".text-danger");
            if (!error) continue;

            const row = error.closest(".admin-form-row");
            if (!row) continue;

            const field = row.querySelector("input, select, textarea");
            if (field) return field;
        }

        return null;
    }

    // Run scanner immediately on load to handle server-side errors returned from Django
    const firstErrorField = getFirstErrorField();
    if (firstErrorField) {
        openErrorTab(firstErrorField);
    }
});