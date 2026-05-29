/**
 * CRM Lead Navigation, Mutation, and Modal Management System
 * Handles lead lists, inline profile switching, automated telephonics integration, and layout filtering.
 */

// Global Application Tracking States
let leadIds = [];
let currentIndex = 0;
let isEditMode = false;

// ==========================================
// LIFECYCLE INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", function () {
    initLeadNavigation();
    initUI();
    initDatePickers();
    initEventListeners();
});

/**
 * Focuses first record context structures upon interface loading lifecycle steps
 */
function initUI() {
    const firstRow = document.querySelector(".lead-row");
    if (firstRow) {
        loadLead(firstRow.dataset.id);
    }
}

/**
 * Sets up Date Range Pickers and Input Masks (Requires jQuery + Plugins)
 */
function initDatePickers() {
    if (typeof $ === "undefined") {
        console.error("jQuery framework is missing. Date pickers and masks cannot initialize.");
        return;
    }

    // Inline form element configurations
    initDatePicker('#ld_dob', false, false);
    initDatePicker('#followup', false, true);
    if ($.fn.inputmask) {

        applyDateMask('#ld_dob');

        $('#followup').inputmask(
            "99/99/9999 99:99",
            {
                placeholder: "DD/MM/YYYY HH:mm",
                clearIncomplete: true
            }
        );

    } else {
        console.warn("Inputmask not loaded");
    }

    // Modal view initialization structures
    initModalPickers();
}

function initDatePicker(selector, isRange = false, withTime = false) {
    if (!$(selector).length) return;

    $(selector).daterangepicker({
        singleDatePicker: !isRange,
        showDropdowns: true,
        autoUpdateInput: false,
        timePicker: withTime,
        timePicker24Hour: true,
        locale: {
            format: withTime ? 'DD/MM/YYYY HH:mm' : 'DD/MM/YYYY'
        }
    });

    $(selector).on('apply.daterangepicker', function (ev, picker) {
        let formatStr = withTime ? 'DD/MM/YYYY HH:mm' : 'DD/MM/YYYY';
        if (isRange) {
            $(this).val(picker.startDate.format(formatStr) + ' - ' + picker.endDate.format(formatStr));
        } else {
            $(this).val(picker.startDate.format(formatStr));
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
 * Initializes secondary modal configurations using separate action callbacks
 */
function initModalPickers() {
    // Follow up tracking element picker config
    $('#modal_followup').daterangepicker({
        singleDatePicker: true,
        timePicker: true,
        timePicker24Hour: true,
        autoUpdateInput: false,
        locale: {
            format: 'DD/MM/YYYY HH:mm'
        }
    });

    $('#modal_followup').on('apply.daterangepicker', function (ev, picker) {
        $(this).val(picker.startDate.format('DD/MM/YYYY HH:mm'));
    });

    $('#modal_followup').on('cancel.daterangepicker', function () {
        $(this).val('');
    });

    // DOB registration date picker config
    $('#modal_dob').daterangepicker({
        singleDatePicker: true,
        showDropdowns: true,
        autoUpdateInput: false,
        locale: {
            format: 'DD/MM/YYYY'
        }
    });

    $('#modal_dob').on('apply.daterangepicker', function (ev, picker) {
        $(this).val(picker.startDate.format('DD/MM/YYYY'));
    });

    $('#modal_dob').on('cancel.daterangepicker', function () {
        $(this).val('');
    });
}

/**
 * Maps static DOM lead collection IDs to the primary iteration state arrays
 */
function initLeadNavigation() {
    leadIds = Array.from(document.querySelectorAll(".lead-row"))
        .map(el => el.dataset.id);
}

/**
 * Attaches standard click events and configures API bindings
 */
function initEventListeners() {
    // Individual layout row active highlight configurations
    document.querySelectorAll(".lead-row").forEach(card => {
        card.addEventListener("click", function () {
            document.querySelectorAll(".lead-row").forEach(c => c.classList.remove("active"));
            this.classList.add("active");
            loadLead(this.dataset.id);
        });
    });

    // Secondary table panel extraction control actions
    document.querySelectorAll(".open-btn").forEach(btn => {
        btn.addEventListener("click", function (e) {
            e.stopPropagation();
            loadLead(this.dataset.id);
        });
    });

    // Telephony Smartflo integration delegation
    $(document).on("click", ".click-to-call-btn", function () {
        let mobile = $(this).data("mobile");
        executeSmartfloDialer(mobile);
    });

    // Intercept Modal Creation Submissions
    $('#leadForm').on('submit', function (e) {
        e.preventDefault();
        handleModalFormSubmit(this);
    });
}

// ==========================================
// TELEPHONY & DIALER ENGINE INTEGRATIONS
// ==========================================
function executeSmartfloDialer(mobile) {
    if (!mobile) return;

    $.ajax({
        url: "/crm/api/test-smartflo/",
        type: "POST",
        headers: {
            "X-CSRFToken": getCSRF()
        },
        data: {
            mobile: mobile
        },
        success: function (response) {
            console.log(response);
            if (response.status === "success") {
                alert("Call Initiated");
            } else {
                alert(response.message || "Call Failed");
            }
        },
        error: function (xhr) {
            console.error(xhr.responseText);
            alert("Server Error");
        }
    });
}

// ==========================================
// CORE LAYOUT DATA RETRIEVAL PIPELINE
// ==========================================
function loadLead(id) {
    const loader = document.getElementById("leadLoader");
    if (loader) loader.style.display = "flex";

    currentIndex = leadIds.indexOf(String(id));

    fetch(`/crm/lead/${id}/`)
        .then(res => res.json())
        .then(data => {
            // Header information population layouts
            setValue("ld_name", data.name);
            setValue("ld_mobile", data.mobile);
            setValue("ld_status", data.status);

            // Left profiling details configurations
            setValue("ld_location", data.location);
            setValue("ld_company", data.company);
            setValue("ld_salary", data.salary);
            setValue("ld_employment_type", data.employment_type);
            setValue("ld_cc_details", data.existing_cc_details);

            // Descriptive metadata panel updates
            setValue("ld_description", data.description);

            // Auxiliary timestamp tracking blocks updating
            setValue("ld_last_updated", data.last_updated);
            setValue("ld_assign_to", data.assigned_to);

            const noteEl = document.getElementById("note");
            if (noteEl) noteEl.value = data.note || '';

            const statusDrp = document.getElementById("ld_status_drp");
            if (statusDrp) statusDrp.value = data.status_key;

            const dialerLink = document.getElementById("dailercallLink");
            if (dialerLink) dialerLink.href = `tel:${data.mobile}`;

            highlightRow(id);
        })
        .catch(err => console.error("Error evaluating profile block configurations:", err))
        .finally(() => {
            if (loader) loader.style.display = "none";
        });
}

// ==========================================
// LIST STEPPER PAGINATION CONTROLS
// ==========================================
function nextLead() {
    if (currentIndex < leadIds.length - 1) {
        currentIndex++;
        loadLead(leadIds[currentIndex]);
    }
}

function prevLead() {
    if (currentIndex > 0) {
        currentIndex--;
        loadLead(leadIds[currentIndex]);
    }
}

/**
 * Asserts structural element properties dynamically across types
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
// MUTATION SUBMISSION & FORM MANAGEMENT
// ==========================================
function toggleEdit() {
    const fields = document.querySelectorAll(
        "#ld_location,#ld_company,#ld_mobile_no,#ld_salary,#ld_name,#ld_employment_type,#ld_cc_details, #followup"
    );

    const btn = document.getElementById("editBtn");
    if (!btn) return;

    if (!isEditMode) {
        fields.forEach(el => el.removeAttribute("disabled"));
        btn.innerText = "Cancel";
        btn.classList.remove("btn-outline-primary");
        btn.classList.add("btn-outline-danger");
        isEditMode = true;
    } else {
        fields.forEach(el => el.setAttribute("disabled", true));

        let leadId = getSelected();
        if (leadId) {
            loadLead(leadId);
        }

        btn.innerText = "Edit";
        btn.classList.remove("btn-outline-danger");
        btn.classList.add("btn-outline-primary");
        isEditMode = false;
    }
}

function saveLead() {
    let leadId = getSelected();
    if (!leadId) return;

    let fu = document.getElementById("followup")?.value;
    if (fu && !isValidDateTime(fu)) {
        alert("Invalid Follow-up format! Valid Format is DD/MM/YYYY HH:mm");
        return;
    }

    let data = new URLSearchParams();
    data.append("lead_id", leadId);
    data.append("name", document.getElementById("ld_name")?.value || "");
    data.append("location", document.getElementById("ld_location")?.value || "");
    data.append("company", document.getElementById("ld_company")?.value || "");
    data.append("salary", document.getElementById("ld_salary")?.value || "");
    data.append("status", document.getElementById("ld_status_drp")?.value || "");
    data.append("note", document.getElementById("note")?.value || "");
    data.append("follow_date", convertToBackendDateTime(document.getElementById("followup")?.value));
    data.append("employment_type", document.getElementById("ld_employment_type")?.value || "");
    data.append("existing_cc_details", document.getElementById("ld_cc_details")?.value || "");

    fetch("/crm/lead/update-full/", {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": getCSRF()
        },
        body: data.toString()
    })
        .then(res => res.json())
        .then((updated) => {
            if (updated.status === "error") {
                alert(updated.message || "Unauthorized access. Please refresh.");
                location.reload();
                return;
            }
            alert("Saved successfully");

            // Sync local list elements natively
            document.querySelectorAll(`[data-id='${leadId}']`).forEach(row => {
                let nameCell = row.querySelector("td:first-child, h6");
                if (nameCell) nameCell.innerText = updated.name;

                let badge = row.querySelector(".badge");
                if (badge) badge.innerText = updated.status_label;

                let fuCell = row.children[2];
                if (fuCell && updated.follow_up_date) {
                    fuCell.innerText = formatToUI(updated.follow_up_date.split("T")[0]);
                }
            });

            const headerStatusBadge = document.getElementById("ld_status");
            if (headerStatusBadge) headerStatusBadge.innerText = updated.status_label;

            document.querySelectorAll(
                "#ld_location,#ld_company,#ld_mobile_no,#ld_salary,#ld_name,#ld_employment_type,#ld_cc_details, #followup"
            ).forEach(el => el.setAttribute("disabled", true));

            const editBtn = document.getElementById("editBtn");
            if (editBtn) {
                editBtn.innerText = "Edit";
                editBtn.classList.remove("btn-outline-danger");
                editBtn.classList.add("btn-outline-primary");
            }

            isEditMode = false;
            loadLead(leadId);
        })
        .catch(err => console.error("Error mutating profile attributes changes:", err));
}

/**
 * Handles creation payload logic processing modal submission forms via AJAX targets
 */
function handleModalFormSubmit(formElement) {
    let formData = $(formElement).serializeArray();

    // Map verification structures for Follow Up entries
    let fuField = formData.find(f => f.name === "follow_up_date");
    if (fuField && fuField.value) {
        if (!moment(fuField.value, "DD/MM/YYYY HH:mm", true).isValid()) {
            alert("Invalid Follow-up Date format (Use DD/MM/YYYY HH:mm)");
            return;
        }
        fuField.value = convertToBackendDateTime(fuField.value);
    }

    // Map structural conversions validation updates for Date of Birth inputs
    let dobField = formData.find(f => f.name === "dob");
    if (dobField && dobField.value) {
        if (!moment(dobField.value, "DD/MM/YYYY", true).isValid()) {
            alert("Invalid DOB format (Use DD/MM/YYYY)");
            return;
        }
        dobField.value = moment(dobField.value, "DD/MM/YYYY").format("YYYY-MM-DD");
    }

    // Capture Django Template URL compilation via script parsing parameters or fixed strings
    // If external file processing strips dynamic tags, switch parameter directly to text endpoints "/crm/lead/api/create/"
    let submitTargetUrl = "/crm/lead/api/create/";

    $.ajax({
        url: submitTargetUrl,
        type: "POST",
        data: $.param(formData),
        success: function (response) {
            alert("Lead Created Successfully");
            $('#leadModal').modal('hide');
            $('#leadForm')[0].reset();
            $('#modal_followup').val('');

            setTimeout(function () {
                location.reload();
            }, 300);
        },
        error: function (xhr) {
            console.error("EX_MODAL_CREATE_FAILURE:", xhr.responseText);
            alert("Error creating lead");
        }
    });
}

// ==========================================
// SEARCH, VISUAL HIGHLIGHTS, & FILTERS Actions
// ==========================================
function highlightRow(id) {
    document.querySelectorAll(".lead-row").forEach(r => r.classList.remove("table-primary"));
    const selectedRow = document.querySelector(`[data-id='${id}']`);
    if (selectedRow) selectedRow.classList.add("table-primary");
}

function updateTableStatus(leadId, status) {
    let row = document.querySelector(`[data-id='${leadId}']`);
    if (row) {
        let statusCell = row.children[4];
        if (statusCell) {
            statusCell.innerHTML = `<span class="badge badge-warning">${status}</span>`;
        }
    }
}

function getSelected() {
    return document.querySelector(".table-primary")?.dataset.id;
}

function applySearch() {
    let val = document.getElementById("searchInput")?.value || "";
    window.location.href = `?search=${encodeURIComponent(val)}`;
}

function applyFilter() {
    let status = document.getElementById("statusFilter")?.value || "";
    let leadSource = document.getElementById("leadSourceFilter")?.value || "";
    window.location.href = `?status=${encodeURIComponent(status)}&lead_source=${encodeURIComponent(leadSource)}`;
}

function sortTable(field) {
    window.location.href = `?sort=${encodeURIComponent(field)}`;
}

// ==========================================
// UTILITY ENGINE CONVERSION ASSERTERS
// ==========================================
function convertToBackendDate(dateStr) {
    if (!dateStr) return '';
    return moment(dateStr, "DD/MM/YYYY").format("YYYY-MM-DD");
}

function convertToBackendDateTime(dateStr) {
    if (!dateStr) return '';
    return moment(dateStr, "DD/MM/YYYY HH:mm").format("YYYY-MM-DDTHH:mm");
}

function isValidDate(dateStr) {
    return moment(dateStr, "DD/MM/YYYY", true).isValid();
}

function isValidDateTime(dateStr) {
    return moment(dateStr, "DD/MM/YYYY HH:mm", true).isValid();
}

function formatToUI(dateStr) {
    if (!dateStr) return '';
    return moment(dateStr, "YYYY-MM-DD").format("DD/MM/YYYY");
}

function maskLast4(value) {
    if (!value) return "";
    value = value.toString();
    if (value.length <= 4) return value;
    return "X".repeat(value.length - 4) + value.slice(-4);
}

function getCSRF() {
    try {
        return document.cookie.split('; ')
            .find(row => row.startsWith('csrftoken='))
            .split('=')[1];
    } catch (e) {
        console.warn("CSRF token verification lookup bypassed or failed inside context cookie.");
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