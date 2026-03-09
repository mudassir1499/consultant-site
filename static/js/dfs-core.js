/* ══════════════════════════════════════════════════════════════════
   DFS Education — Core JavaScript
   Shared across all templates (public + authenticated)
   ══════════════════════════════════════════════════════════════════ */

(function() {
    'use strict';

    /* ─── Page Loader ────────────────────────────────────────────── */
    window.addEventListener('load', function() {
        var loader = document.getElementById('pageLoader');
        if (loader) {
            loader.classList.add('fade-out');
            setTimeout(function() { loader.remove(); }, 300);
        }
    });

    /* ─── Navbar Scroll Effect ───────────────────────────────────── */
    var navbar = document.querySelector('.dfs-navbar');
    if (navbar) {
        function checkScroll() {
            if (window.scrollY > 20) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        }
        window.addEventListener('scroll', checkScroll, { passive: true });
        checkScroll();
    }

    /* ─── DOMContentLoaded ───────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', function() {

        /* Auto-show loading modal for forms with data-loading */
        document.querySelectorAll('form[data-loading]').forEach(function(form) {
            form.addEventListener('submit', function() {
                var msg = form.getAttribute('data-loading') || 'Processing...';
                showLoadingModal(msg);
            });
        });

        /* File upload progress bars */
        document.querySelectorAll('input[type="file"]').forEach(function(input) {
            var wrapper = document.createElement('div');
            wrapper.className = 'upload-progress-wrapper';
            wrapper.innerHTML = '<div class="progress" style="height:5px;"><div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width:0%;background:var(--dfs-blue,#2B7DE9)"></div></div><small class="text-muted upload-status mt-1 d-block"></small>';
            input.parentNode.appendChild(wrapper);

            input.addEventListener('change', function() {
                if (input.files.length > 0) {
                    var file = input.files[0];
                    var sizeMB = (file.size / (1024 * 1024)).toFixed(2);
                    wrapper.classList.add('active');
                    wrapper.querySelector('.progress-bar').style.width = '100%';
                    wrapper.querySelector('.upload-status').textContent = file.name + ' (' + sizeMB + ' MB) — Ready';
                } else {
                    wrapper.classList.remove('active');
                }
            });
        });

        /* XHR upload progress for multipart forms */
        document.querySelectorAll('form[enctype="multipart/form-data"]').forEach(function(form) {
            form.addEventListener('submit', function(e) {
                var hasFiles = false;
                form.querySelectorAll('input[type="file"]').forEach(function(inp) {
                    if (inp.files.length > 0) hasFiles = true;
                });
                if (!hasFiles) return;

                e.preventDefault();
                showLoadingModal('Uploading files...');
                var progressBar = document.querySelector('#loadingModalProgress .progress-bar');

                var xhr = new XMLHttpRequest();
                xhr.open(form.method || 'POST', form.action || window.location.href, true);

                xhr.upload.addEventListener('progress', function(ev) {
                    if (ev.lengthComputable) {
                        var pct = Math.round((ev.loaded / ev.total) * 100);
                        if (progressBar) progressBar.style.width = pct + '%';
                        var msg = document.getElementById('loadingModalMessage');
                        if (msg) msg.textContent = 'Uploading... ' + pct + '%';
                    }
                });

                xhr.addEventListener('load', function() {
                    if (xhr.status >= 200 && xhr.status < 400) {
                        window.location.href = xhr.responseURL || window.location.href;
                    } else {
                        hideLoadingModal();
                        alert('Upload failed. Please try again.');
                    }
                });

                xhr.addEventListener('error', function() {
                    hideLoadingModal();
                    alert('Network error. Please try again.');
                });

                xhr.send(new FormData(form));
            });
        });

        /* Animated counter for stats */
        var counters = document.querySelectorAll('[data-count]');
        if (counters.length > 0) {
            var observer = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        animateCounter(entry.target);
                        observer.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.3 });
            counters.forEach(function(el) { observer.observe(el); });
        }
    });

    /* ─── Counter Animation ──────────────────────────────────────── */
    function animateCounter(el) {
        var target = parseInt(el.getAttribute('data-count'), 10);
        var suffix = el.getAttribute('data-suffix') || '';
        var duration = 2000;
        var start = 0;
        var startTime = null;

        function step(timestamp) {
            if (!startTime) startTime = timestamp;
            var progress = Math.min((timestamp - startTime) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
            var current = Math.floor(eased * target);
            el.textContent = current + suffix;
            if (progress < 1) requestAnimationFrame(step);
            else el.textContent = target + suffix;
        }
        requestAnimationFrame(step);
    }

    /* ─── Modal Helpers (global) ─────────────────────────────────── */
    window.showLoadingModal = function(message) {
        var msgEl = document.getElementById('loadingModalMessage');
        if (msgEl) msgEl.textContent = message || 'Processing...';
        var bar = document.querySelector('#loadingModalProgress .progress-bar');
        if (bar) bar.style.width = '0%';
        var el = document.getElementById('loadingModal');
        if (el && typeof bootstrap !== 'undefined') {
            new bootstrap.Modal(el).show();
        }
    };

    window.hideLoadingModal = function() {
        var el = document.getElementById('loadingModal');
        if (el && typeof bootstrap !== 'undefined') {
            var modal = bootstrap.Modal.getInstance(el);
            if (modal) modal.hide();
        }
    };

    window.showSuccessModal = function(title, message) {
        var titleEl = document.getElementById('successModalTitle');
        var msgEl = document.getElementById('successModalMessage');
        if (titleEl) titleEl.textContent = title || 'Success!';
        if (msgEl) msgEl.textContent = message || 'Action completed successfully.';
        var el = document.getElementById('actionSuccessModal');
        if (el && typeof bootstrap !== 'undefined') {
            new bootstrap.Modal(el).show();
        }
    };

})();
