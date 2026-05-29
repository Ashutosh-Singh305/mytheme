$(document).ready(function () {
    // Setup dynamic Bootstrap classes 
    $('form input[type="text"]:not(.filter-input), form input[type="password"], form input[type="email"], form select:not(.available-box):not(.chosen-box)').addClass('form-control');

    // ✅ Unified Dynamic Password Toggle Engine
    $('.toggle-password-btn').on('click', function () {
        const targetId = $(this).data('target');
        const $passwordField = $(targetId);

        if ($passwordField.length) {
            const type = $passwordField.attr('type') === 'password' ? 'text' : 'password';
            $passwordField.attr('type', type);
            $(this).find('i').toggleClass('fa-eye fa-eye-slash');
        }
    });

    // --- DUAL LIST BOX MOTOR LOGIC ---
    function initializeDualListbox(selectorId) {
        const $container = $(selectorId);

        $container.find('.move-right').on('click', function () {
            $container.find('.available-box option:selected').appendTo($container.find('.chosen-box'));
        });

        $container.find('.move-left').on('click', function () {
            $container.find('.chosen-box option:selected').appendTo($container.find('.available-box'));
        });

        $container.find('.selector-chooseall').on('click', function (e) {
            e.preventDefault();
            $container.find('.available-box option').appendTo($container.find('.chosen-box'));
        });

        $container.find('.selector-clearall').on('click', function (e) {
            e.preventDefault();
            $container.find('.chosen-box option').appendTo($container.find('.available-box'));
        });

        $container.find('.filter-input').on('keyup', function () {
            const value = $(this).val().toLowerCase();
            $(this).closest('.selector-available, .selector-chosen').find('select option').filter(function () {
                $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1);
            });
        });
    }

    initializeDualListbox('#groups_selector');
    initializeDualListbox('#permissions_selector');

    // Auto-select all choices inside chosen boxes immediately before POST submission 
    $('#user-reg-form').on('submit', function () {
        $('.chosen-box option').prop('selected', true);
    });
});