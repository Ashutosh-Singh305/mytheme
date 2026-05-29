(function($) {
  'use strict';

  if ($(".select2-single").length) {
    $(".select2-single").select2({
      width: '100%',
      allowClear: true,
      placeholder: 'Select....',
    });
  }

  if ($(".select2-multiple").length) {
    $(".select2-multiple").select2({
      width: '100%',
      allowClear: true,
      placeholder: 'Select....',
    });
  }

})(jQuery);