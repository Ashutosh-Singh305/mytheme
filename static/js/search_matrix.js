/**
 * Advanced Search Canvas Handler
 */
$(document).ready(function () {
    const urlInterfaceParameters = new URLSearchParams(window.location.search);
    const searchTargetQuery = urlInterfaceParameters.get('q');
    let localizedDatasetRegistry = {};

    if (!searchTargetQuery) {
        $('#matrix-pane-loading').addClass('d-none');
        $('#matrix-pane-fallback').removeClass('d-none').find('p').text("Please provide a search term.");
        return;
    }

    // Display string term representation inside visual frame
    $('#query-string-highlight').text(searchTargetQuery);

    // Hydrate backend lookup dataset maps
    $.ajax({
        url: '/crm/api/global-search/',
        type: 'GET',
        data: { q: searchTargetQuery },
        dataType: 'json',
        success: function (data) {
            localizedDatasetRegistry = data.results;
            $('#matrix-pane-loading').addClass('d-none');
            
            buildSidebarFacets();
            executeScopeDisplay('all');
        },
        error: function () {
            $('#matrix-pane-loading').addClass('d-none');
            $('#matrix-pane-fallback').removeClass('d-none').find('p').text("Error retrieving records from search directory.");
        }
    });

    function buildSidebarFacets() {
        const filterControlsWrapper = $('#matrix-sidebar-filters');
        
        Object.keys(localizedDatasetRegistry).forEach(modelKey => {
            const countRecords = localizedDatasetRegistry[modelKey].length;
            if (countRecords === 0) return;

            const structuredTitle = modelKey.replace(/_/g, ' ');
            const dynamicFacetButton = $(`
                <button type="button" data-scope="${modelKey}" class="search-filter-btn btn w-100 text-start p-1 border-0 text-sm rounded-2 text-secondary bg-transparent hover-bg-light">
                    <i class="bi bi-collection-fill me-2 text-muted"></i> ${structuredTitle}
                    <span class="badge bg-primary  float-end rounded-pill mt-0.5"">${countRecords}</span>
                </button>
            `);
            filterControlsWrapper.append(dynamicFacetButton);
        });

        // Setup filter button triggers
        $('.search-filter-btn').on('click', function () {
            $('.search-filter-btn').removeClass('active');
            $(this).addClass('active');
            executeScopeDisplay($(this).data('scope'));
        });
    }

    function executeScopeDisplay(scopeTarget) {
        const outputDeck = $('#matrix-cards-deck');
        outputDeck.empty();

        let structuralMatchHits = false;

        Object.keys(localizedDatasetRegistry).forEach(modelKey => {
            const rawRecords = localizedDatasetRegistry[modelKey];
            if (rawRecords.length === 0) return;
            
            // Apply sidebar filtering logic
            if (scopeTarget !== 'all' && scopeTarget !== modelKey) return;

            structuralMatchHits = true;
            const modelBeautified = modelKey.replace(/_/g, ' ');

            let groupContainer = $(`
                <div class="card border-0 shadow-sm overflow-hidden animate-fade-in">
                    <div class="bg-primary round-3 p-1  d-flex align-items-center justify-content-between">
                        <h5 class="m-0 font-semibold text-sm text-uppercase tracking-wider">${modelBeautified}</h5>
                        <span class="badge badge-info rounded-pill small">${rawRecords.length} records found</span>
                    </div>
                    <ul class="list-group list-group-flush" id="group-list-${modelKey}"></ul>
                </div>
            `);

            outputDeck.append(groupContainer);
            const explicitListHook = $(`#group-list-${modelKey}`);

            rawRecords.forEach(recordItem => {
                const itemTargetRoute = `/crm/${modelKey}/${recordItem.id}/`;
                let recordRowItem = $(`
                    <li class="list-group-item list-group-item-action border-light-subtle transition-all">
                        <a href="${itemTargetRoute}" class="text-decoration-none d-flex align-items-center justify-content-between">
                            <div>
                                <h6 class="text-primary mb-1 fw-semibold">${recordItem.label}</h6>
                                <span class="text-muted d-block small">Database Reference Key: #${recordItem.id}</span>
                            </div>
                            <div class="btn btn-sm btn-outline-light border text-muted">Open Record <i class="bi bi-chevron-right ms-1"></i></div>
                        </a>
                    </li>
                `);
                explicitListHook.append(recordRowItem);
            });
        });

        if (!structuralMatchHits) {
            $('#matrix-pane-fallback').removeClass('d-none');
        } else {
            $('#matrix-pane-fallback').addClass('d-none');
        }
    }
});