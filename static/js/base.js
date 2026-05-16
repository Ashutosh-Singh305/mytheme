const sidebar = document.getElementById("sidebar");
const mainContent = document.getElementById("mainContent");
const toggleBtn = document.getElementById("toggleSidebar");
const overlay = document.getElementById("overlay");

toggleBtn.addEventListener("click", function () {

    // MOBILE
    if (window.innerWidth < 992) {

        sidebar.classList.toggle("mobile-show");
        overlay.classList.toggle("show");

    }

    // DESKTOP
    else {

        sidebar.classList.toggle("collapsed");
        mainContent.classList.toggle("expanded");

    }

});

// Close mobile sidebar
overlay.addEventListener("click", function () {

    sidebar.classList.remove("mobile-show");
    overlay.classList.remove("show");

});
// ADD THIS BELOW YOUR EXISTING JS

const closeSidebar = document.getElementById("closeSidebar");

closeSidebar.addEventListener("click", function () {

    sidebar.classList.remove("mobile-show");
    overlay.classList.remove("show");

});

// ===============================
// GLOBAL PAGE SEARCH
// ===============================

const globalSearch = document.getElementById("globalSearch");

globalSearch.addEventListener("keyup", function () {

    const searchValue = this.value.toLowerCase();

    // SEARCH ONLY CONTENT AREA
    const searchableItems = document.querySelectorAll(
        ".content-wrapper .card, \
         .content-wrapper table tbody tr, \
         .content-wrapper p, \
         .content-wrapper h1, \
         .content-wrapper h2, \
         .content-wrapper h3, \
         .content-wrapper h4, \
         .content-wrapper h5, \
         .content-wrapper h6"
    );

    searchableItems.forEach(item => {

        const text = item.innerText.toLowerCase();

        if (text.includes(searchValue)) {
            item.style.display = "";
        } else {
            item.style.display = "none";
        }

    });

});