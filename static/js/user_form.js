$(document).ready(function () {
    
    // ==========================================================================
    // 1. GLOBAL UI & UTILITY INITIALIZATIONS
    // ==========================================================================
    
    // Dynamic Bootstrap class styling setup for standard form fields
    const genericInputSelectors = [
        'form input[type="text"]:not(.filter-input)',
        'form input[type="password"]',
        'form input[type="email"]',
        'form select:not(.available-box):not(.chosen-box):not(.custom-modern-select)'
    ].join(', ');
    
    $(genericInputSelectors).addClass('form-control');

    // Unified Dynamic Password Toggle Engine
    $('.toggle-password-btn').on('click', function () {
        const targetId = $(this).data('target');
        const $passwordField = $(targetId);

        if ($passwordField.length) {
            const type = $passwordField.attr('type') === 'password' ? 'text' : 'password';
            $passwordField.attr('type', type);
            $(this).find('i').toggleClass('fa-eye fa-eye-slash');
        }
    });

    // ==========================================================================
    // 2. CENTRALIZED DUAL LIST BOX COMPONENT MOTOR
    // ==========================================================================
    function initializeDualListbox(selectorId) {
        const $container = $(selectorId);
        if (!$container.length) return;

        const $availableBox = $container.find('.available-box');
        const $chosenBox    = $container.find('.chosen-box');
        const $placeholder  = $container.find('.empty-placeholder-view');

        // Dynamic State Engine: Updates numerical status badges & visibility states
        function updateUIState() {
            const totalAvailable = $availableBox.find('option').length;
            const totalChosen    = $chosenBox.find('option').length;

            $container.find('#available-counter').text(totalAvailable);
            $container.find('#chosen-counter').text(totalChosen);

            // Display or drop the decorative "No permissions selected" placeholder graphics
            if (totalChosen === 0) {
                $placeholder.removeClass('d-none');
            } else {
                $placeholder.addClass('d-none');
            }
        }

        // --- BUTTON ACTIONS (Click to Move Selected Options) ---
        $container.find('.move-right').on('click', function (e) {
            e.preventDefault();
            $availableBox.find('option:selected').appendTo($chosenBox).prop('selected', false);
            updateUIState();
        });

        $container.find('.move-left').on('click', function (e) {
            e.preventDefault();
            $chosenBox.find('option:selected').appendTo($availableBox).prop('selected', false);
            updateUIState();
        });

        // --- LINK ACTIONS (Mass Updates) ---
        $container.find('.selector-chooseall').on('click', function (e) {
            e.preventDefault();
            $availableBox.find('option:not([style*="display: none"])').appendTo($chosenBox);
            updateUIState();
        });

        $container.find('.selector-clearall').on('click', function (e) {
            e.preventDefault();
            $chosenBox.find('option:not([style*="display: none"])').appendTo($availableBox);
            updateUIState();
        });

        // --- INTERACTIVE SHORTCUTS (Double-click to Move Items Immediately) ---
        $availableBox.on('dblclick', 'option', function() {
            $(this).appendTo($chosenBox).prop('selected', false);
            updateUIState();
        });

        $chosenBox.on('dblclick', 'option', function() {
            $(this).appendTo($availableBox).prop('selected', false);
            updateUIState();
        });

        // --- REAL-TIME DATA FILTER SEARCHING ENGINE ---
        $container.find('.filter-input').on('keyup', function () {
            const queryValue = $(this).val().toLowerCase();
            // Works fluidly across both legacy `.selector-available` and modern component cards
            const $targetCard = $(this).closest('.modern-selector-card, .selector-available, .selector-chosen');
            
            $targetCard.find('select option').filter(function () {
                $(this).toggle($(this).text().toLowerCase().indexOf(queryValue) > -1);
            });
        });

        // Initial setup pass run to synchronize badge counts on template load
        updateUIState();
    }

    // Initialize all app list instances safely
    initializeDualListbox('#groups_selector');
    initializeDualListbox('#permissions_selector');

    // ==========================================================================
    // 3. SUBMISSION DATA INTEGRITY ASSURANCE
    // ==========================================================================
    
    // Auto-select choices right before submit so Django intercepts all fields in the array
    $('#user-reg-form, #group-reg-form').on('submit', function () {
        $(this).find('.chosen-box option').prop('selected', true);
    });
});