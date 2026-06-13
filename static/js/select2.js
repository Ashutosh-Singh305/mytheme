(function($) {
  'use strict';

  // Define a reusable initialization function
  window.initGlobalSelect2 = function(context) {
    // Look within a specific context, or default to the whole document
    var $scope = context ? $(context) : $(document);

    if ($scope.find(".select2-single").length) {
      $scope.find(".select2-single").select2({
        theme: 'bootstrap-5',
        width: '100%',
        allowClear: true,
        placeholder: 'Select....',
      });
    }

    if ($scope.find(".select2-multiple").length) {
      $scope.find(".select2-multiple").select2({
        theme: 'bootstrap-5',
        width: '100%',
        allowClear: true,
        placeholder: 'Select....',
      });
    }
  };

  // Run automatically on initial page load
  $(document).ready(function() {
    window.initGlobalSelect2();
  });

})(jQuery);