document.addEventListener("DOMContentLoaded", function () {

    const ifscField = document.querySelector("#id_ifsc_code");
    const branchField = document.querySelector("#id_branch_name");

    if (!ifscField || !branchField) return;

    //fetch branch
    function fetchBranch(ifsc) {
        fetch(`/crm/api/get-branch/?ifsc=${ifsc}`)
            .then(response => response.json())
            .then(data => {
                if (data.branch_name) {
                    branchField.value = data.branch_name;
                } else if (data.branch) {
                    branchField.value = data.branch;
                } else {
                    branchField.value = "";
                }
            })
            .catch(err => {
                console.error("IFSC fetch error:", err);
            });
    }

    // Page load (IFSC present, branch empty)
    const initialIfsc = ifscField.value.trim();
    const initialBranch = branchField.value.trim();

    if (initialIfsc && !initialBranch) {
        fetchBranch(initialIfsc);
    }

    let debounceTimer;

    // typing IFSC
    ifscField.addEventListener("input", function () {
        clearTimeout(debounceTimer);

        const ifsc = this.value.trim();

        //If both blank → do nothing
        if (!ifsc) {
            branchField.value = "";
            return;
        }

        debounceTimer = setTimeout(() => {
            fetchBranch(ifsc);
        }, 500);
    });
});