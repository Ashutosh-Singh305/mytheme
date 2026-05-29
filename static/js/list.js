// =====================================
// Generic AJAX List View Handler
// =====================================

class AjaxListView {

    constructor(config = {}) {

        this.tableContainer =
            document.querySelector(
                config.tableContainer || "#tableContainer"
            );

        this.searchInput =
            document.querySelector(
                config.searchInput || "#myInput"
            );

        this.filterSelector =
            config.filterSelector || ".list-filter";

        this.sortSelector =
            config.sortSelector || ".sort";

        this.paginationSelector =
            config.paginationSelector || ".page-link";

        this.currentPage = 1;

        this.currentSort =
            config.currentSort || "id";

        this.currentDir =
            config.currentDir || "desc";

        this.search =
            this.searchInput?.value || "";

        this.filters = {};

        this.init();
    }

    init() {

        this.initFilters();
        this.initSearch();
        this.initSorting();
        this.initPagination();

        this.updateSortIcons();
    }

    // -------------------
    // FILTERS
    // -------------------
    initFilters() {

        const filters =
            document.querySelectorAll(
                this.filterSelector
            );

        filters.forEach(filter => {

            this.filters[
                filter.name
            ] = filter.value;

            filter.addEventListener(
                "change",
                () => {

                    this.filters[
                        filter.name
                    ] = filter.value;

                    this.currentPage = 1;

                    this.loadData();
                }
            );
        });
    }

    // -------------------
    // SEARCH
    // -------------------
    initSearch() {

        if (!this.searchInput) return;

        let timer;

        this.searchInput
            .addEventListener(
                "keyup",
                () => {

                    clearTimeout(timer);

                    timer = setTimeout(
                        () => {

                            this.search =
                                this.searchInput.value;

                            this.currentPage = 1;

                            this.loadData();

                        },
                        400
                    );
                }
            );
    }

    // -------------------
    // SORTING
    // -------------------
    initSorting() {

        document.addEventListener(
            "click",
            (e) => {

                const btn =
                    e.target.closest(
                        this.sortSelector
                    );

                if (!btn) return;

                e.preventDefault();

                const field =
                    btn.dataset.field;

                if (
                    this.currentSort === field
                ) {

                    this.currentDir =
                        this.currentDir === "asc"
                            ? "desc"
                            : "asc";

                } else {

                    this.currentSort =
                        field;

                    this.currentDir =
                        "asc";
                }

                this.loadData();
            }
        );
    }

    // -------------------
    // PAGINATION
    // -------------------
    initPagination() {

        document.addEventListener(
            "click",
            (e) => {

                const btn =
                    e.target.closest(
                        this.paginationSelector
                    );

                if (!btn) return;

                e.preventDefault();

                this.currentPage =
                    btn.dataset.page;

                this.loadData();
            }
        );
    }

    // -------------------
    // SORT ICONS
    // -------------------
    updateSortIcons() {

        document.querySelectorAll(
            ".sort-icon"
        ).forEach(icon => {

            icon.classList.remove(
                "fa-sort-up",
                "fa-sort-down"
            );

            icon.classList.add(
                "fa-sort"
            );
        });

        const active =
            document.querySelector(
                `.sort[data-field='${this.currentSort}'] .sort-icon`
            );

        if (active) {

            active.classList.remove(
                "fa-sort"
            );

            active.classList.add(
                this.currentDir === "asc"
                    ? "fa-sort-up"
                    : "fa-sort-down"
            );
        }
    }

    // -------------------
    // AJAX
    // -------------------
    loadData() {

        const loader =
            document.querySelector("#loader");

        const tableContent =
            document.querySelector("#tableContent");

        loader.style.display = "flex";

        const params =
            new URLSearchParams({

                page: this.currentPage,
                sort: this.currentSort,
                dir: this.currentDir,
                search: this.search,
                ...this.filters
            });

        fetch(
            `${window.location.pathname}?${params}`,
            {
                headers: {
                    "X-Requested-With":
                        "XMLHttpRequest"
                }
            }
        )
            .then(res => res.text())
            .then(html => {

                const parser =
                    new DOMParser();

                const doc =
                    parser.parseFromString(
                        html,
                        "text/html"
                    );

                const newContent =
                    doc.querySelector(
                        "#tableContent"
                    );

                if (newContent) {

                    tableContent.innerHTML =
                        newContent.innerHTML;
                }

                this.updateSortIcons();
            })
            .finally(() => {

                loader.style.display =
                    "none";
            });
    }
}