// ==========================================
//        SIDEBAR & INTERACTIVE NAVIGATION   
// ==========================================
const sidebar = document.getElementById("sidebar");
const mainContent = document.getElementById("mainContent");
const toggleBtn = document.getElementById("toggleSidebar");
const overlay = document.getElementById("overlay");

if (toggleBtn) {
  toggleBtn.addEventListener("click", function () {
    // MOBILE
    if (window.innerWidth < 992) {
      if (sidebar) sidebar.classList.toggle("mobile-show");
      if (overlay) overlay.classList.toggle("show");
    }
    // DESKTOP
    else {
      if (sidebar) sidebar.classList.toggle("collapsed");
      if (mainContent) mainContent.classList.toggle("expanded");
    }
  });
}

// Close mobile sidebar
if (overlay) {
  overlay.addEventListener("click", function () {
    if (sidebar) sidebar.classList.remove("mobile-show");
    if (overlay) overlay.classList.remove("show");
  });
}

const closeSidebar = document.getElementById("closeSidebar");
if (closeSidebar) {
  closeSidebar.addEventListener("click", function () {
    if (sidebar) sidebar.classList.remove("mobile-show");
    if (overlay) overlay.classList.remove("show");
  });
}
// ==========================================
//         PERSISTENT BOOTSTRAP TABS         
// ==========================================
document.addEventListener("DOMContentLoaded", function () {
  const tabs = document.querySelectorAll('button[data-bs-toggle="tab"]');

  // Check if the page execution type is a hard browser refresh
  const entryType = window.performance.getEntriesByType("navigation")[0]?.type;
  const isRefresh = entryType === "reload";

  if (isRefresh) {
    // Only attempt to restore the last tab if the user triggered a reload/refresh
    const activeTab = sessionStorage.getItem("activeUserTab");
    if (activeTab) {
      const triggerEl = document.querySelector(`button[data-bs-target="${activeTab}"]`);
      if (triggerEl) {
        const tabInstance = bootstrap.Tab.getOrCreateInstance(triggerEl);
        tabInstance.show();
      }
    }
  } else {
    // If it's a fresh visit, wipe out any old tab history so it safely defaults to tab #1
    sessionStorage.removeItem("activeUserTab");
  }

  // Continuously save the active tab tracking state when a user switches tabs
  tabs.forEach(tab => {
    tab.addEventListener("shown.bs.tab", function () {
      sessionStorage.setItem("activeUserTab", this.getAttribute("data-bs-target"));
    });
  });
});


// ==========================================
//       REAL-TIME NOTIFICATIONS SYSTEM      
// ==========================================
(function () {
  "use strict";

  let notificationAudio = null;

  // Initialize system once DOM is ready
  document.addEventListener("DOMContentLoaded", () => {
    loadNotifications();
    initWebSocket();
    initClickHandlers();
    initMarkAllRead();
  });

  /**
   * Fetch and render dropdown notifications and badges
   */
  async function loadNotifications() {
    try {
      const res = await fetch("/api/notifications/");
      if (!res.ok) throw new Error("Failed to fetch notifications");

      const data = await res.json();
      const countEls = document.querySelectorAll(".notif-count");
      const listEls = document.querySelectorAll(".notif-items");

      // Update unread count badges
      countEls.forEach(el => {
        if (data.unread_count > 0) {
          el.textContent = data.unread_count;
          el.classList.remove("d-none");
        } else {
          el.classList.add("d-none");
        }
      });

      // Update notification dropdown lists
      listEls.forEach(listEl => {
        listEl.innerHTML = "";

        if (!data.items || !data.items.length) {
          listEl.innerHTML = `<p class="text-center text-muted py-3 mb-0 small">No notifications</p>`;
          return;
        }

        data.items.forEach(n => {
          const div = document.createElement("a");
          div.className = `dropdown-item preview-item notification-item ${!n.is_read ? "notification-unread" : ""}`;
          div.href = n.url || "#";
          div.dataset.id = n.id;
          div.dataset.url = n.url || "";

          div.innerHTML = `
            <div class="preview-item-content py-2">
              <p class="font-weight-medium text-dark mb-1">${n.title}</p>
              <p class="small-text mb-0">${n.message}</p>
            </div>
          `;
          listEl.appendChild(div);
        });
      });
    } catch (err) {
      console.error("Error loading notifications:", err);
    }
  }

  /**
   * Click event delegation for individual notification items
   */
  function initClickHandlers() {
    document.addEventListener("click", function (e) {
      if (e.target.closest(".float-notif")) {
        return;
      }

      const item = e.target.closest(".notification-item");
      if (!item) return;

      e.preventDefault();

      const notificationId = item.dataset.id;
      const redirectUrl = item.dataset.url;

      // Optimistic UI update
      item.classList.remove("notification-unread");

      fetch(`/api/notifications/read/${notificationId}/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
          "Content-Type": "application/json"
        },
      }).finally(() => {
        if (redirectUrl) {
          window.location.href = redirectUrl;
        }
      });
    });
  }

  /**
   * Setup click handler for "Mark All As Read" shared buttons across headers
   */
  function initMarkAllRead() {
    // Delegated click implementation targeting the shared interface class
    document.addEventListener("click", async function (e) {
      const btn = e.target.closest(".mark-all-read-shared");
      if (!btn) return;

      e.preventDefault();
      try {
        const res = await fetch("/api/notifications/mark-all-read/", {
          method: "POST",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "Content-Type": "application/json"
          },
        });

        if (res.ok) {
          loadNotifications();
        }
      } catch (err) {
        console.error("Error marking all notifications as read:", err);
      }
    });
  }

  /**
   * Initialize Real-time WebSocket connection
   */
  function initWebSocket() {
    const isLocalhost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const wsPort = isLocalhost ? "8002" : window.location.port;
    const wsPortString = wsPort ? `:${wsPort}` : "";

    const socket = new WebSocket(
      `${protocol}://${window.location.hostname}${wsPortString}/ws/notifications/`
    );

    socket.onmessage = function (event) {
      try {
        const data = JSON.parse(event.data);

        // Refresh layouts data
        loadNotifications();

        // Show interactive notification popup banner
        showFloatingNotification(data.title, data.message, data.url, data.id);

        // Audible alert
        playNotificationSound();
      } catch (err) {
        console.error("Error processing WebSocket message data:", err);
      }
    };

    socket.onclose = function () {
      console.warn("Notification socket closed.");
    };

    socket.onerror = function (e) {
      console.error("WebSocket error observed:", e);
    };
  }

  /**
   * Generates a temporary clickable floating alert notification on screen
   */
  function showFloatingNotification(title, message, url = "", id = "") {
    const box = document.createElement("div");
    box.className = "float-notif";
    if (url) box.style.cursor = "pointer";

    box.innerHTML = `
      <span class="close">&times;</span>
      <h6>${title}</h6>
      <p>${message}</p>
    `;

    box.addEventListener("click", (e) => {
      if (url) {
        window.location.href = url;
      }
    });

    let timer = setTimeout(() => box.remove(), 10000);

    box.addEventListener("mouseenter", () => clearTimeout(timer));
    box.addEventListener("mouseleave", () => {
      timer = setTimeout(() => box.remove(), 5000);
    });

    box.querySelector(".close").onclick = e => {
      e.stopPropagation();
      box.remove();
    };

    document.body.appendChild(box);
  }

  /**
   * Plays a sound snippet upon incoming real-time socket events
   */
  function playNotificationSound() {
    if (!notificationAudio) {
      notificationAudio = new Audio("/static/sounds/notification.wav");
      notificationAudio.volume = 0.6;
    }

    notificationAudio.currentTime = 0;
    notificationAudio.play().catch(() => {
      console.warn("Notification sound blocked by browser autoplay policy.");
    });
  }

  /**
   * Helper utility to grab CSRF security tokens from document cookies
   */
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + "=")) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
})();


// ==========================================
//          SELECT2 ENGINE DEFINITION        
// ==========================================
(function ($) {
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


// ==========================================
//       JQUERY DYNAMIC LAYOUT CONTROL       
// ==========================================
$(document).ready(function () {
  // 1. FAB Click Event for toggle mutation switching
  $('#layoutSwitchFab').on('click', function () {
    if ($('body').hasClass('layout-horizontal')) {
      $('body').removeClass('layout-horizontal').addClass('layout-vertical');
      localStorage.setItem('user-menu-layout', 'vertical');
    } else {
      $('body').removeClass('layout-vertical').addClass('layout-horizontal');
      localStorage.setItem('user-menu-layout', 'horizontal');
    }
  });

  // 2. Keep text inputs synchronized between the duplicate horizontal/vertical search bars
  $('.sync-search-value').on('input', function () {
    $('.sync-search-value').not(this).val($(this).val());
  });

  // 3. Handle shared notifications behavior UI updates instantly
  $(document).on('click', '.mark-all-read-shared', function (e) {
    e.preventDefault();
    $('.notif-items').html('<p class="text-center text-muted py-3 mb-0 small">No notifications</p>');
    $('.notif-count').addClass('d-none').text('0');
  });
});



/**
 * Salesforce Global Realtime Autocomplete Engine (Fixed Multi-Layout Integration)
 */
$(document).ready(function () {
    let searchDebounceTracker = null;

    $('.sync-search-value').on('input', function () {
        const value = $(this).val();

        // 1. Instantly mirror text inputs across all layout variants
        $('.sync-search-value').not(this).val(value);

        clearTimeout(searchDebounceTracker);

        if (value.trim().length < 3) {
            $('.search-floating-dropdown').addClass('d-none');
            return;
        }

        // 2. Clear out older hits and present the loader in both panels simultaneously
        $('.search-dropdown-results').html(`
            <div class="text-center py-3 text-muted small">
                <div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div>
                Searching secure directory...
            </div>
        `);
        $('.search-floating-dropdown').removeClass('d-none');

        // 3. Debounce API request
        searchDebounceTracker = setTimeout(() => {
            $.ajax({
                url: '/crm/api/global-search/',
                type: 'GET',
                data: { q: value.trim() },
                dataType: 'json',
                success: function (response) {
                    // Independently loop through and hydrate each dropdown instance cleanly
                    $('.search-floating-dropdown').each(function() {
                        const targetPane = $(this).find('.search-dropdown-results');
                        renderAutocompleteDropdown(response.results, value.trim(), targetPane);
                    });
                },
                error: function () {
                    $('.search-dropdown-results').html(
                        '<div class="p-3 text-center text-danger small"><i class="bi bi-exclamation-triangle-fill me-1"></i> Data processing fault.</div>'
                    );
                }
            });
        }, 300);
    });

    function renderAutocompleteDropdown(results, rawQuery, targetPane) {
        targetPane.empty();
        const models = Object.keys(results);

        if (models.length === 0) {
            targetPane.html(`<div class="p-3 text-center text-muted small">No matches for "${rawQuery}"</div>`);
            return;
        }

        models.forEach(modelKey => {
            const listRecords = results[modelKey];
            if (listRecords.length === 0) return;

            const cleanHeader = modelKey.replace(/_/g, ' ');

            let structuralHeader = $(`
                <div class="dropdown-header text-uppercase text-primary fw-bold tracking-wider small bg-light rounded-2 py-1 px-2 mt-2 mb-1 text-start">
                    ${cleanHeader}
                </div>
            `);
            targetPane.append(structuralHeader);

            listRecords.forEach(item => {
                const targetEndpoint = `/crm/${modelKey}/${item.id}/`;
                let entryLink = $(`
                    <a class="dropdown-item d-flex align-items-center py-2 px-3 rounded-2 text-wrap text-start" href="${targetEndpoint}">
                        <div class="flex-grow-1 min-w-0">
                            <div class="text-dark fw-medium small text-truncate">${item.label}</div>
                            <span class="text-muted tracking-tight" style="font-size: 0.75rem;">System Reference ID: #${item.id}</span>
                        </div>
                        <i class="bi bi-arrow-up-right-short text-muted ms-auto"></i>
                    </a>
                `);
                targetPane.append(entryLink);
            });
        });

        let explorationTrigger = $(`
            <div class="border-top pt-2 mt-2">
                <a href="/crm/search/?q=${encodeURIComponent(rawQuery)}" class="btn btn-sm btn-primary d-block text-center text-white fw-medium font-sm py-1.5">
                    Launch Advanced Search Canvas »
                </a>
            </div>
        `);
        targetPane.append(explorationTrigger);
    }

    // Hide dropdowns when clicking anywhere outside of a search input component wrapper
    $(document).on('click', function (event) {
        if (!$(event.target).closest('.position-relative').find('.search-floating-dropdown').length) {
            $('.search-floating-dropdown').addClass('d-none');
        }
    });

    // Capture the 'Enter' key to redirect to full canvas search
    $('.sync-search-value').on('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const payload = $(this).val().trim();
            if (payload.length >= 3) {
                window.location.href = `/crm/search/?q=${encodeURIComponent(payload)}`;
            }
        }
    });
});