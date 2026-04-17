(function () {
  'use strict';

  const SLIDE_DURATION = 6000;

  document.addEventListener('DOMContentLoaded', () => {
    initScrollProgress();
    initHeader();
    initNav();
    initCarousel();
    initReveal();
    initCounters();
    initActiveNavHighlight();
  });

  // ===== Scroll progress bar =====
  function initScrollProgress() {
    const bar = document.getElementById('scrollProgress');
    if (!bar) return;
    const update = () => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const pct = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
      bar.style.width = pct + '%';
    };
    update();
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
  }

  // ===== Header scroll state =====
  function initHeader() {
    const header = document.getElementById('siteHeader');
    if (!header) return;
    const toggle = () => header.classList.toggle('is-scrolled', window.scrollY > 16);
    toggle();
    window.addEventListener('scroll', toggle, { passive: true });
  }

  // ===== Mobile nav drawer =====
  function initNav() {
    const toggle = document.getElementById('navToggle');
    const nav = document.getElementById('globalNav');
    if (!toggle || !nav) return;
    const close = () => {
      nav.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-label', 'メニューを開く');
    };
    toggle.addEventListener('click', () => {
      const open = nav.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'メニューを閉じる' : 'メニューを開く');
    });
    nav.querySelectorAll('a').forEach(a => a.addEventListener('click', close));
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  }

  // ===== Hero carousel =====
  function initCarousel() {
    const track = document.getElementById('carouselTrack');
    const prev = document.getElementById('carouselPrev');
    const next = document.getElementById('carouselNext');
    const indicators = document.getElementById('carouselIndicators');
    if (!track || !prev || !next || !indicators) return;

    const slides = Array.from(track.children);
    const count = slides.length;
    if (count === 0) return;
    let current = 0;
    let timer = null;
    let paused = false;

    // Build indicators
    indicators.innerHTML = '';
    slides.forEach((_, i) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'carousel-indicator';
      btn.setAttribute('role', 'tab');
      btn.setAttribute('aria-label', `スライド ${i + 1} を表示`);
      const fill = document.createElement('span');
      fill.className = 'carousel-indicator-fill';
      btn.appendChild(fill);
      btn.addEventListener('click', () => goTo(i));
      indicators.appendChild(btn);
    });
    document.documentElement.style.setProperty('--slide-duration', (SLIDE_DURATION / 1000) + 's');

    const indicatorEls = Array.from(indicators.children);

    function render() {
      track.style.transform = `translateX(-${current * 100}%)`;
      slides.forEach((s, i) => s.classList.toggle('is-active', i === current));
      indicatorEls.forEach((el, i) => {
        el.classList.toggle('active', i === current);
        // Restart the fill animation on the active indicator
        const fill = el.querySelector('.carousel-indicator-fill');
        if (fill) {
          fill.style.animation = 'none';
          // Force reflow to restart animation
          // eslint-disable-next-line no-unused-expressions
          fill.offsetHeight;
          fill.style.animation = '';
        }
      });
    }

    function goTo(index) {
      current = (index + count) % count;
      render();
      restartTimer();
    }
    function nextSlide() { goTo(current + 1); }
    function prevSlide() { goTo(current - 1); }

    function startTimer() {
      stopTimer();
      if (paused) return;
      timer = setTimeout(nextSlide, SLIDE_DURATION);
    }
    function stopTimer() {
      if (timer) { clearTimeout(timer); timer = null; }
    }
    function restartTimer() {
      stopTimer();
      startTimer();
    }

    prev.addEventListener('click', prevSlide);
    next.addEventListener('click', nextSlide);

    // Keyboard
    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') prevSlide();
      else if (e.key === 'ArrowRight') nextSlide();
    });

    // Pause on hover / focus
    const carousel = track.parentElement;
    const pause = () => { paused = true; stopTimer(); };
    const resume = () => { paused = false; startTimer(); };
    carousel.addEventListener('mouseenter', pause);
    carousel.addEventListener('mouseleave', resume);
    carousel.addEventListener('focusin', pause);
    carousel.addEventListener('focusout', resume);

    // Pause when tab hidden
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) { paused = true; stopTimer(); }
      else { paused = false; startTimer(); }
    });

    // Touch swipe
    let touchStartX = 0;
    let touchDeltaX = 0;
    carousel.addEventListener('touchstart', (e) => {
      touchStartX = e.touches[0].clientX;
      touchDeltaX = 0;
      pause();
    }, { passive: true });
    carousel.addEventListener('touchmove', (e) => {
      touchDeltaX = e.touches[0].clientX - touchStartX;
    }, { passive: true });
    carousel.addEventListener('touchend', () => {
      if (Math.abs(touchDeltaX) > 50) {
        if (touchDeltaX < 0) nextSlide(); else prevSlide();
      }
      resume();
    });

    render();
    startTimer();
  }

  // ===== IntersectionObserver reveal =====
  function initReveal() {
    const targets = document.querySelectorAll('.reveal');
    if (!('IntersectionObserver' in window) || targets.length === 0) {
      targets.forEach(el => el.classList.add('is-visible'));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.15 });
    targets.forEach(el => io.observe(el));
  }

  // ===== Counter animation =====
  function initCounters() {
    const counters = document.querySelectorAll('[data-count]');
    if (counters.length === 0) return;
    if (!('IntersectionObserver' in window)) {
      counters.forEach(el => {
        el.textContent = el.dataset.count + (el.dataset.suffix || '');
      });
      return;
    }
    const animate = (el) => {
      const target = parseInt(el.dataset.count, 10) || 0;
      const suffix = el.dataset.suffix || '';
      const duration = 1400;
      const startTime = performance.now();
      const step = (now) => {
        const progress = Math.min((now - startTime) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(target * eased) + suffix;
        if (progress < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          animate(entry.target);
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.4 });
    counters.forEach(el => io.observe(el));
  }

  // ===== Active nav highlight =====
  function initActiveNavHighlight() {
    const links = document.querySelectorAll('.global-nav a[href^="#"]');
    if (links.length === 0) return;
    const map = new Map();
    links.forEach(link => {
      const id = link.getAttribute('href').slice(1);
      const section = document.getElementById(id);
      if (section) map.set(section, link);
    });
    if (map.size === 0) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        const link = map.get(entry.target);
        if (!link) return;
        if (entry.isIntersecting) {
          links.forEach(l => l.classList.remove('is-active'));
          link.classList.add('is-active');
        }
      });
    }, { rootMargin: '-40% 0px -55% 0px', threshold: 0 });
    map.forEach((_, section) => io.observe(section));
  }
})();
