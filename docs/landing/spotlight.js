/**
 * Spotlight Glow — Mouse tracker
 *
 * Attaches mousemove listeners to all .spotlight-card elements
 * and updates --mouse-x / --mouse-y CSS custom properties.
 *
 * Usage:
 *   <link rel="stylesheet" href="spotlight.css">
 *   <script src="spotlight.js"></script>
 *
 * Or import as module:
 *   import "./spotlight.css";
 *   import "./spotlight.js";
 */

(function () {
  "use strict";

  /**
   * Initialize spotlight tracking on all matching elements.
   * Call this once on DOMContentLoaded, or after dynamically
   * adding spotlight-card elements.
   */
  function initSpotlight() {
    var cards = document.querySelectorAll(".spotlight-card");

    cards.forEach(function (card) {
      // Skip if already initialized
      if (card.dataset.spotlightInit) return;
      card.dataset.spotlightInit = "1";

      card.addEventListener("mousemove", function (e) {
        var rect = card.getBoundingClientRect();
        var x = e.clientX - rect.left;
        var y = e.clientY - rect.top;

        card.style.setProperty("--mouse-x", x + "px");
        card.style.setProperty("--mouse-y", y + "px");
      });
    });
  }

  // Initialize on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSpotlight);
  } else {
    initSpotlight();
  }

  // Expose for dynamic content
  window.initSpotlight = initSpotlight;
})();
