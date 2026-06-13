/**
 * CRM Candidate Navigation and Management System
 * Handles candidate listing, inline data updates, form modes, and date utility formatting.
 */

// Global Application State Variables
let candidateIds = [];
let currentIndex = 0;
let currentCandidateId = null;
let previousCandidateId = null;
let isEditMode = false;

// ==========================================
// LIFECYCLE INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", function () {
    initCandidateNavigation();
    initUI();
    initDatePickers();
    initEventListeners();
});

/**
 * Initial view and row layout constraints setup
 */
function initUI() {
    const firstRow = document.querySelector(".candidate-row");
    if (firstRow) {
        selectCandidate(firstRow.dataset.id);
    }
    
    const mobileRow = document.getElementById("mobileFieldRow");
    if (mobileRow) {
        mobileRow.style.display = "none";
    }
}

/**
 * Set up Date Range Pickers and Input Masks (Requires jQuery + Plugins)
 */
function initDatePickers() {
    if (typeof $ === "undefined") {
        console.error("jQuery is missing. Date pickers and masks cannot initialize.");
        return;
    }

    // Initialize pickers
    initDatePicker('#ld_calling_date');
    initDatePicker('#id_doj');
    initDatePicker('#ld_interview_date');

    // Apply masks
    // applyDateMask('#ld_calling_date');
    // applyDateMask('#id_doj');
    // applyDateMask('#ld_interview_date');
}

function initDatePicker(selector, isRange = false) {
    if (!$(selector).length) return;

    $(selector).daterangepicker({
        singleDatePicker: !isRange,
        showDropdowns: true,
        autoUpdateInput: false,
        locale: {
            format: 'DD/MM/YYYY'
        }
    });

    $(selector).on('apply.daterangepicker', function (ev, picker) {
        if (isRange) {
            $(this).val(
                picker.startDate.format('DD/MM/YYYY') + ' - ' + picker.endDate.format('DD/MM/YYYY')
            );
        } else {
            $(this).val(picker.startDate.format('DD/MM/YYYY'));
        }
    });
}

function applyDateMask(selector) {
    if (!$(selector).length) return;

    $(selector).inputmask("99/99/9999", {
        placeholder: "DD/MM/YYYY",
        clearIncomplete: true
    });
}

/**
 * Map initial DOM candidate rows to application tracking array
 */
function initCandidateNavigation() {
    candidateIds = Array.from(document.querySelectorAll(".candidate-row"))
        .map(el => el.dataset.id);
}

/**
 * Set up dynamic table row event listeners
 */
function initEventListeners() {
    document.querySelectorAll(".candidate-row").forEach(card => {
        card.addEventListener("click", function () {
            selectCandidate(this.dataset.id);
        });
    });

    const searchInput = document.getElementById("candidateSearch");
    if (searchInput) {
        searchInput.addEventListener("keypress", function (e) {
            if (e.key === "Enter") {
                applyCandidateSearch();
            }
        });
    }
}

// ==========================================
// CORE DATA PIPELINE HANDLING
// ==========================================

/**
 * Focus and trigger pipeline routines for chosen candidate
 */
function selectCandidate(id) {
    currentCandidateId = id;
    highlightCandidate(id);
    loadCandidate(id);
}

/**
 * Render visually active table elements
 */
function highlightCandidate(id) {
    document.querySelectorAll(".candidate-row")
        .forEach(r => r.classList.remove("active", "table-info"));

    document.querySelectorAll(`[data-id='${id}']`)
        .forEach(row => {
            row.classList.add("active", "table-info");
        });
}

/**
 * Fetch Candidate profiles from API endpoints
 */
function loadCandidate(id) {
    const loader = document.getElementById("candidateLoader");
    if (loader) loader.style.display = "flex";

    currentIndex = candidateIds.indexOf(String(id));

    fetch(`/crm/candidate/${id}/`)
        .then(res => {
            if (!res.ok) throw new Error("Network candidate retrieval failed");
            return res.json();
        })
        .then(data => {
            // Header updating mapping
            setValue("ld_name", data.name);
            setValue("ld_mobile", data.mobile);
            setValue("ld_mobile_form", data.mobile);
            setValue("ld_applied_for", data.position_applied_for);
            setValue("ld_experince", data.experince);

            // Left panel values mapping
            setValue("ld_candidate_status", data.candidate_status);
            setValue("id_candidate_area", data.candidate_area);
            setValue("ld_calling_date", formatToUI(data.calling_date));
            setValue("ld_source", data.source);

            // Right panel column mapping
            setValue("ld_interview_date", formatToUI(data.interview_date));
            setValue("id_doj", formatToUI(data.date_of_joining));
            setValue("ld_modified_date", data.modified_date);
            setValue("ld_status", data.candidate_status);
            setValue("ld_assign_to", data.assigned_to);
            setValue("ld_modified_by", data.modified_by);
            setValue("ld_recruiter", data.recruiter_id);

            const noteEl = document.getElementById("note");
            if (noteEl) noteEl.value = data.note || '';

            const callLink = document.getElementById("callLink");
            if (callLink) callLink.href = `tel:${data.mobile}`;
        })
        .catch(err => console.error("Error updating views data blocks:", err))
        .finally(() => {
            if (loader) loader.style.display = "none";
        });
}

// ==========================================
// PAGINATION STEPPERS
// ==========================================
function nextCandidate() {
    if (currentIndex < candidateIds.length - 1) {
        currentIndex++;
        selectCandidate(candidateIds[currentIndex]);
    }
}

function preCandidate() {
    if (currentIndex > 0) {
        currentIndex--;
        selectCandidate(candidateIds[currentIndex]);
    }
}

function applySearch() {
    let val = document.getElementById("searchInput")?.value || "";
    window.location.href = `?search=${encodeURIComponent(val)}`;
}

/**
 * Safe HTML Element value parsing matching tagName properties
 */
function setValue(id, value) {
    let el = document.getElementById(id);
    if (!el) return;

    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT") {
        el.value = value || '';
    } else {
        el.innerText = value || '-';
    }
}

// ==========================================
// MUTATION ACTION WRAPPERS
// ==========================================

/**
 * Creates and Cancels "New Creation Form States" handling layout toggles
 */
function handleNewCancel() {
    const btn = document.getElementById("newBtn");
    if (!btn) return;

    // ===== IF CLICKING "NEW" =====
    if (!btn.classList.contains("is-cancel")) {
        previousCandidateId = currentCandidateId;
        resetCandidateForm();

        btn.classList.add("is-cancel");
        btn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
        btn.classList.remove("btn-outline-primary");
        btn.classList.add("btn-outline-danger");
    } 
    // ===== IF CLICKING "CANCEL" =====
    else {
        if (previousCandidateId) {
            selectCandidate(previousCandidateId);
        }

        isEditMode = false;

        // DISABLE ALL EDITABLE FIELDS
        document.querySelectorAll(
            "#id_doj,#ld_calling_date,#ld_interview_date,#ld_modified_date,#ld_source,#id_candidate_area,#ld_experince,#ld_applied_for,#ld_name"
        ).forEach(el => el.setAttribute("disabled", true));

        const recruiterField = document.getElementById("ld_recruiter");
        if (recruiterField) recruiterField.setAttribute("disabled", true);

        toggleRowDisplay("assignRow", "flex");
        toggleRowDisplay("modifiedRow", "flex");
        toggleRowDisplay("lastUpdatedRow", "flex");

        // RESET ACTIONS BUTTONS
        const editBtn = document.getElementById("editBtn");
        if (editBtn) {
            editBtn.innerText = "Edit";
            editBtn.classList.remove("btn-outline-danger");
            editBtn.classList.add("btn-outline-primary");
            editBtn.disabled = false;
        }

        disableNavigationButtons(false);
        toggleRowDisplay("mobileFieldRow", "none");

        // RESET NEW BUTTON
        btn.classList.remove("is-cancel");
        btn.innerHTML = '<i class="fa-solid fa-plus"></i>';
        btn.classList.remove("btn-outline-danger");
        btn.classList.add("btn-outline-primary");

        currentCandidateId = previousCandidateId;
        previousCandidateId = null;
    }
}

function resetCandidateForm() {
    toggleRowDisplay("mobileFieldRow", "flex");

    previousCandidateId = currentCandidateId;
    currentCandidateId = null;
    currentIndex = -1;
    isEditMode = true;

    // CLEAR INPUT FIELDS
    document.querySelectorAll(
        "#id_doj,#ld_calling_date,#ld_mobile_form,#ld_recruiter,#ld_interview_date,#ld_modified_date,#ld_source,#id_candidate_area,#ld_experince,#ld_applied_for,#ld_name,#note,#ld_candidate_status"
    ).forEach(el => {
        if (el.tagName === "SELECT") {
            el.selectedIndex = 0;
        } else {
            el.value = "";
        }
    });

    toggleRowDisplay("assignRow", "none");
    toggleRowDisplay("modifiedRow", "none");
    toggleRowDisplay("lastUpdatedRow", "none");

    // CLEAR LAYOUT HEADERS
    setValue("ld_mobile", "-");
    setValue("ld_status", "-");
    setValue("ld_assign_to", "");
    setValue("ld_modified_by", "");

    // REMOVE ACTIVE SELECTIONS
    document.querySelectorAll(".candidate-row")
        .forEach(r => r.classList.remove("active", "table-info"));

    // ENABLE FIELDS
    document.querySelectorAll(
        "#id_doj,#ld_calling_date,#ld_mobile_form,#ld_interview_date,#ld_modified_date,#ld_source,#id_candidate_area,#ld_experince,#ld_applied_for,#ld_name"
    ).forEach(el => el.removeAttribute("disabled"));
    
    const recruiterField = document.getElementById("ld_recruiter");
    if (recruiterField) recruiterField.removeAttribute("disabled");

    // UPDATE ACTIONS STATES
    const newBtn = document.getElementById("newBtn");
    if (newBtn) {
        newBtn.classList.add("is-cancel");
        newBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
        newBtn.classList.remove("btn-outline-primary");
        newBtn.classList.add("btn-outline-danger");
    }

    disableNavigationButtons(true);
}

/**
 * Submit profile attributes via standard Form Requests to Server Route Targets
 */
function saveCandidate() {
        let isCreate = !currentCandidateId;

        let url = isCreate
            ? "/crm/candidate/create/"
            : "/crm/candidate/update/";

        let data = new URLSearchParams();

        // Only send ID in update mode
        if (!isCreate) {
            data.append("candidate_id", currentCandidateId);
        }

        // ===== VALIDATION =====
        let calling_date = document.getElementById("ld_calling_date").value;
        if (calling_date && !isValidDate(calling_date)) {
            alert("Invalid DOB format! Use DD/MM/YYYY");
            return;
        }

        let interviewDate = document.getElementById("ld_interview_date").value;
        if (interviewDate && !isValidDate(interviewDate)) {
            alert("Invalid Interview Date format!");
            return;
        }

        let doj = document.getElementById("id_doj").value;
        if (doj && !isValidDate(doj)) {
            alert("Invalid DOJ format!");
            return;
        }

        // ===== DATA =====
        data.append("full_name", document.getElementById("ld_name").value);
        data.append("applied_for", document.getElementById("ld_applied_for").value);
        data.append("experience", document.getElementById("ld_experince").value);
        data.append("candidate_status", document.getElementById("ld_candidate_status").value);
        data.append("candidate_area", document.getElementById("id_candidate_area").value);
        data.append("calling_date", convertToBackendDate(calling_date));
        data.append("source", document.getElementById("ld_source").value);
        data.append("modified_date", document.getElementById("ld_modified_date").value);
        data.append("interview_date", convertToBackendDate(interviewDate));
        data.append("doj", convertToBackendDate(doj));
        data.append("phone", document.getElementById("ld_mobile_form").value);
        data.append("note", document.getElementById("note").value);
        data.append("recruiter", document.getElementById("ld_recruiter").value);

        // ===== API CALL =====
        fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": getCSRF()
            },
            body: data.toString()
        })
        .then(res => res.json())
        .then((res) => {

            if (res.status === "error") {
                alert(res.message || "Something went wrong");
                return;
            }

            alert(isCreate ? "Created successfully" : "Updated successfully");

            // ===== CREATE MODE =====
            if (isCreate) {
                location.reload();   // simplest + safe
                return;
            }

            // ===== UPDATE MODE UI UPDATE =====
            document.querySelectorAll(`[data-id='${currentCandidateId}']`).forEach(row => {

                let nameCell = row.querySelector("td:first-child, h6");
                if (nameCell) nameCell.innerText = res.full_name;

                let badge = row.querySelector(".badge");
                if (badge) {
                    badge.innerText = res.candidate_status_label;
                }
            });

            document.getElementById("ld_status").innerText = res.candidate_status_label;

            // Disable fields again
            document.querySelectorAll(
                "#id_doj,#ld_calling_date,#ld_interview_date,#ld_modified_date,#ld_source,#id_candidate_area,#ld_experince,#ld_applied_for,#ld_name,#ld_recruiter"
            ).forEach(el => el.setAttribute("disabled", true));

            // Reset button
            const btn = document.getElementById("editBtn");
            btn.innerText = "Edit";
            btn.classList.remove("btn-outline-danger");
            btn.classList.add("btn-outline-primary");

            isEditMode = false;

            // 🔓 Re-enable NEW button (FIX)
            const newBtn = document.getElementById("newBtn");
            newBtn.disabled = false;
            newBtn.classList.remove("disabled");

            // Reload current candidate
            loadCandidate(currentCandidateId);
        });
    }

/**
 * Toggles layout editing field status properties
 */
function toggleEdit() {
    const fields = document.querySelectorAll(
        "#id_doj,#ld_recruiter,#ld_calling_date,#ld_interview_date,#ld_modified_date,#id_candidate_area,#ld_candidate_status,#ld_experince,#ld_applied_for,#ld_name"
    );

    const btn = document.getElementById("editBtn");
    const newBtn = document.getElementById("newBtn");
    if (!btn) return;

    if (!isEditMode) {
        fields.forEach(el => el.removeAttribute("disabled"));

        btn.innerText = "Cancel";
        btn.classList.remove("btn-outline-primary");
        btn.classList.add("btn-outline-danger");

        if (newBtn) {
            newBtn.disabled = true;
            newBtn.classList.add("disabled");
        }
        isEditMode = true;
    } else {
        fields.forEach(el => el.setAttribute("disabled", true));
        loadCandidate(currentCandidateId);

        btn.innerText = "Edit";
        btn.classList.remove("btn-outline-danger");
        btn.classList.add("btn-outline-primary");

        if (newBtn) {
            newBtn.disabled = false;
            newBtn.classList.remove("disabled");
        }
        isEditMode = false;
    }
}

// ==========================================
// SEARCH & ROUTING NAVIGATION ACTIONS
// ==========================================
function applyCandidateSearch() {
    const input = document.getElementById("candidateSearch");
    if (input) {
        window.location.href = `?search=${encodeURIComponent(input.value)}`;
    }
}

// Security reference mapping handling template spelling variance
function applycandidateSearchh() {
    applyCandidateSearch();
}

function applyFilter() {
    const appliedFor = document.getElementById("appliedForFilter")?.value || "";
    const statusFilter = document.getElementById("candidateStatusfilter")?.value || "";
    window.location.href = `?applied_for=${encodeURIComponent(appliedFor)}&status=${encodeURIComponent(statusFilter)}`;
}

// ==========================================
// DATA ENGINE TRANSFORMATION HELPERS
// ==========================================
function convertToBackendDate(dateStr) {
    if (!dateStr || typeof moment === "undefined") return '';
    return moment(dateStr, "DD/MM/YYYY").format("YYYY-MM-DD");
}

function isValidDate(dateStr) {
    if (typeof moment === "undefined") return true; 
    return moment(dateStr, "DD/MM/YYYY", true).isValid();
}

function formatToUI(dateStr) {
    if (!dateStr || typeof moment === "undefined") return '';
    return moment(dateStr, "YYYY-MM-DD").format("DD/MM/YYYY");
}

function getCSRF() {
    try {
        const csrf = document.cookie.split("; ").find(row => row.startsWith("csrftoken="));
        return csrf ? csrf.split("=")[1] : "";
    } catch (e) {
        console.warn("CSRF token parsing error safely suppressed.");
        return "";
    }
}

function toggleRowDisplay(id, displayType) {
    const el = document.getElementById(id);
    if (el) el.style.display = displayType;
}

function disableNavigationButtons(status) {
    const editBtn = document.getElementById("editBtn");
    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");

    if (editBtn) editBtn.disabled = status;
    if (prevBtn) prevBtn.disabled = status;
    if (nextBtn) nextBtn.disabled = status;
}

function liveValidateMobile(input) {
    input.value = input.value.replace(/[^0-9]/g, '');

    //  Prevent typing more than 10 digits
    if (input.value.length > 10) {
        input.value = input.value.slice(0, 10);
    }

    //  Live Bootstrap Color Validation
    if (input.value.length === 0) {
        // If empty, remove both colors
        input.classList.remove('is-invalid', 'is-valid');
    } else if (input.value.length === 10) {
        // Exactly 10 digits -> Turn GREEN live
        input.classList.remove('is-invalid');
        input.classList.add('is-valid');
    } else {
        // Less than 10 digits -> Turn RED live
        input.classList.remove('is-valid');
        input.classList.add('is-invalid');
    }
}