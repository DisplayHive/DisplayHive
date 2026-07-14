// Click-to-maximize lightbox for documentation screenshots and Mermaid
// diagrams. Deliberately vanilla JS (no plugin dependency) — see
// docs/stylesheets/extra.css for the accompanying `.lightbox-overlay` styles.
//
// Uses event delegation (one listener on `document`) rather than binding to
// each image/diagram individually, since Mermaid renders its SVGs into the
// page asynchronously after load — a per-element binding pass would miss
// diagrams that hadn't rendered yet at bind time.
(function () {
  var IMG_SELECTOR = '.md-content img:not(.brand-logo)';
  var MERMAID_SELECTOR = '.md-content .mermaid svg';

  function getOverlay() {
    var overlay = document.querySelector('.lightbox-overlay');
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.className = 'lightbox-overlay';
    var content = document.createElement('div');
    content.className = 'lightbox-content';
    overlay.appendChild(content);
    document.body.appendChild(overlay);

    overlay.addEventListener('click', function () {
      overlay.classList.remove('is-open');
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') overlay.classList.remove('is-open');
    });

    return overlay;
  }

  function openWithImage(img) {
    var overlay = getOverlay();
    var content = overlay.querySelector('.lightbox-content');
    content.innerHTML = '';
    var clone = document.createElement('img');
    clone.src = img.currentSrc || img.src;
    clone.alt = img.alt || '';
    content.appendChild(clone);
    overlay.classList.add('is-open');
  }

  function openWithSvg(svg) {
    var overlay = getOverlay();
    var content = overlay.querySelector('.lightbox-content');
    content.innerHTML = '';
    var clone = svg.cloneNode(true);
    // Mermaid sets an inline max-width (sized for the inline diagram) that
    // would otherwise override the enlarged sizing in CSS.
    clone.style.maxWidth = '';
    clone.style.height = 'auto';
    content.appendChild(clone);
    overlay.classList.add('is-open');
  }

  document.addEventListener('click', function (event) {
    var img = event.target.closest(IMG_SELECTOR);
    if (img) {
      openWithImage(img);
      return;
    }
    var svg = event.target.closest(MERMAID_SELECTOR);
    if (svg) {
      openWithSvg(svg);
    }
  });
})();
