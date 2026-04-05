/* ═══════════════════════════════════════════
   CUSTOM CURSOR
═══════════════════════════════════════════ */
(function initCursor() {
  const dot  = document.getElementById('cursor-dot');
  const ring = document.getElementById('cursor-ring');
  if (!dot || !ring) return;

  let mouseX = 0, mouseY = 0;
  let ringX  = 0, ringY  = 0;
  let raf;

  document.addEventListener('mousemove', e => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    dot.style.left = mouseX + 'px';
    dot.style.top  = mouseY + 'px';
  });

  function animateRing() {
    ringX += (mouseX - ringX) * 0.12;
    ringY += (mouseY - ringY) * 0.12;
    ring.style.left = ringX + 'px';
    ring.style.top  = ringY + 'px';
    raf = requestAnimationFrame(animateRing);
  }
  animateRing();

  const hoverTargets = 'a, button, .project-card, .credential-card, .edu-card, .highlight-box';
  document.addEventListener('mouseover', e => {
    if (e.target.closest(hoverTargets)) document.body.classList.add('cursor-hover');
  });
  document.addEventListener('mouseout', e => {
    if (e.target.closest(hoverTargets)) document.body.classList.remove('cursor-hover');
  });
})();

/* ═══════════════════════════════════════════
   NAV SCROLL
═══════════════════════════════════════════ */
(function initNav() {
  const nav = document.querySelector('nav');
  if (!nav) return;
  const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 60);
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();

/* ═══════════════════════════════════════════
   HERO — VIDEO SCROLL SCRUB
═══════════════════════════════════════════ */
(function initHeroVideo() {
  const video      = document.getElementById('hero-video');
  const wrapper    = document.getElementById('hero-wrapper');
  const scrollHint = document.getElementById('scroll-hint');
  const progFill   = document.getElementById('vid-progress-fill');

  if (!video || !wrapper) return;

  // Hero text elements — thresholds as fractions (0–1)
  const heroElements = [
    { el: document.querySelector('.hero-eyebrow'), fadeIn: 0,    fadeOut: 0.85 },
    { el: document.querySelector('.hero-name'),    fadeIn: 0.05, fadeOut: 0.85 },
    { el: document.querySelector('.hero-tagline'), fadeIn: 0.12, fadeOut: 0.85 },
    { el: document.querySelector('.hero-stats'),   fadeIn: 0.22, fadeOut: 0.88 },
    { el: document.querySelector('.hero-summary'), fadeIn: 0.22, fadeOut: 0.88 },
    { el: document.querySelector('.hero-ctas'),    fadeIn: 0.32, fadeOut: 0.92 },
  ];

  // Show elements that should be visible at scroll = 0
  heroElements.forEach(({ el, fadeIn, fadeOut }) => {
    if (!el) return;
    if (0 >= fadeIn && 0 < fadeOut) el.classList.add('vis');
  });

  function updateScrollText(progress) {
    heroElements.forEach(({ el, fadeIn, fadeOut }) => {
      if (!el) return;
      if (progress >= fadeIn && progress < fadeOut) {
        el.classList.add('vis');
      } else {
        el.classList.remove('vis');
      }
    });
    if (scrollHint) scrollHint.style.opacity = progress > 0.15 ? '0' : '';
  }

  // Only use the first 3 seconds of the video
  const MAX_SECONDS = 3;

  // Set wrapper height based on capped duration
  // Desktop: ~120vh/s → 3s = 360vh  |  Mobile: ~80vh/s → 3s = 240vh
  function onMetadata() {
    const activeDuration = Math.min(video.duration, MAX_SECONDS);
    const vhPerSecond = window.innerWidth < 768 ? 80 : 120;
    const scrollHeight = Math.max(200, Math.round(activeDuration * vhPerSecond));
    wrapper.style.height = scrollHeight + 'vh';
    video.currentTime = 0;
    setTimeout(() => updateScrollText(0), 300);
  }

  // Handle both: metadata already loaded (readyState >= 1) or not yet
  if (video.readyState >= 1) {
    onMetadata();
  } else {
    video.addEventListener('loadedmetadata', onMetadata, { once: true });
  }

  // Force load on mobile where preload is ignored
  video.load();
  // Play then immediately pause — unlocks currentTime scrubbing on iOS
  const playPromise = video.play();
  if (playPromise !== undefined) {
    playPromise.then(() => video.pause()).catch(() => {});
  }

  // Keep video paused — scroll controls currentTime manually
  video.addEventListener('play', () => {
    if (!video.seeking) video.pause();
  });

  // Scroll scrub
  window.addEventListener('scroll', () => {
    const totalScroll = wrapper.offsetHeight - window.innerHeight;
    const progress = Math.max(0, Math.min(1, window.scrollY / totalScroll));

    // Scrub video (capped to first MAX_SECONDS)
    if (video.readyState >= 2 && video.duration) {
      video.currentTime = progress * Math.min(video.duration, MAX_SECONDS);
    }

    // Gold progress bar
    if (progFill) progFill.style.width = (progress * 100) + '%';

    // Scroll-driven text
    updateScrollText(progress);
  }, { passive: true });
})();

/* ═══════════════════════════════════════════
   INTERSECTION OBSERVER — REVEAL
═══════════════════════════════════════════ */
(function initReveal() {
  const els = document.querySelectorAll('.reveal');
  if (!els.length) return;
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('visible');
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.12 });
  els.forEach(el => observer.observe(el));
})();

/* ═══════════════════════════════════════════
   SKILL BARS
═══════════════════════════════════════════ */
(function initSkillBars() {
  const fills = document.querySelectorAll('.skill-fill');
  if (!fills.length) return;
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        const target = e.target.dataset.pct;
        e.target.style.width = target + '%';
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.5 });
  fills.forEach(f => observer.observe(f));
})();

/* ═══════════════════════════════════════════
   GALLERY LIGHTBOX
═══════════════════════════════════════════ */
function openLightbox(tile) {
  const src = tile.dataset.src;
  const img = document.getElementById('lightbox-img');
  const lb  = document.getElementById('lightbox');
  if (!img || !lb || !src) return;
  img.src = src;
  img.alt = tile.querySelector('img') ? tile.querySelector('img').alt : '';
  lb.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeLightbox() {
  const lb  = document.getElementById('lightbox');
  const img = document.getElementById('lightbox-img');
  if (!lb) return;
  lb.classList.remove('open');
  document.body.style.overflow = '';
  if (img) img.src = '';
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });

/* ═══════════════════════════════════════════
   SMOOTH SCROLL for nav links
═══════════════════════════════════════════ */
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const id = a.getAttribute('href').slice(1);
    const target = document.getElementById(id);
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});
