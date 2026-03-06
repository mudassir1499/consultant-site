/**
 * DFS Education - Shared Utilities
 * Toast notifications, AJAX helpers, bulk actions, keyboard shortcuts, CSV export
 */

(function(window) {
    'use strict';

    // ═══════════════════════════════════════════════════════════════════
    // CSRF Token
    // ═══════════════════════════════════════════════════════════════════
    function getCSRFToken() {
        // Try meta tag first, then cookie
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var c = cookies[i].trim();
            if (c.startsWith('csrftoken=')) return c.substring('csrftoken='.length);
        }
        return '';
    }

    // ═══════════════════════════════════════════════════════════════════
    // TOAST NOTIFICATIONS
    // ═══════════════════════════════════════════════════════════════════
    var toastContainer = null;
    var toastCounter = 0;

    function ensureToastContainer() {
        if (!toastContainer) {
            toastContainer = document.getElementById('dfs-toast-container');
            if (!toastContainer) {
                toastContainer = document.createElement('div');
                toastContainer.id = 'dfs-toast-container';
                toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
                toastContainer.style.zIndex = '11000';
                document.body.appendChild(toastContainer);
            }
        }
        return toastContainer;
    }

    var TOAST_ICONS = {
        success: 'bi-check-circle-fill text-success',
        error: 'bi-exclamation-triangle-fill text-danger',
        danger: 'bi-exclamation-triangle-fill text-danger',
        warning: 'bi-exclamation-circle-fill text-warning',
        info: 'bi-info-circle-fill text-primary'
    };

    function showToast(message, type, duration) {
        type = type || 'info';
        duration = duration || 5000;
        var container = ensureToastContainer();
        var id = 'dfs-toast-' + (++toastCounter);
        var icon = TOAST_ICONS[type] || TOAST_ICONS.info;
        var borderColor = type === 'error' ? 'danger' : type;

        var html = '<div id="' + id + '" class="toast border-start border-4 border-' + borderColor + ' shadow-sm" role="alert" data-bs-autohide="true" data-bs-delay="' + duration + '">' +
            '<div class="toast-body d-flex align-items-center gap-2 py-3 px-3">' +
            '<i class="bi ' + icon + ' fs-5"></i>' +
            '<span class="flex-grow-1">' + message + '</span>' +
            '<button type="button" class="btn-close btn-close-sm ms-2" data-bs-dismiss="toast"></button>' +
            '</div></div>';

        container.insertAdjacentHTML('beforeend', html);
        var toastEl = document.getElementById(id);
        var bsToast = new bootstrap.Toast(toastEl);
        bsToast.show();
        toastEl.addEventListener('hidden.bs.toast', function() { toastEl.remove(); });
        return bsToast;
    }

    // Convert Django messages (already in DOM) to toasts
    function convertMessagesToToasts() {
        var alerts = document.querySelectorAll('.alert.alert-dismissible');
        alerts.forEach(function(alert) {
            var text = alert.textContent.trim().replace(/\s+/g, ' ');
            var type = 'info';
            if (alert.classList.contains('alert-success')) type = 'success';
            else if (alert.classList.contains('alert-danger') || alert.classList.contains('alert-error')) type = 'error';
            else if (alert.classList.contains('alert-warning')) type = 'warning';
            showToast(text, type, 6000);
            alert.remove();
        });
    }

    // ═══════════════════════════════════════════════════════════════════
    // FETCH JSON HELPER (CSRF-aware)
    // ═══════════════════════════════════════════════════════════════════
    function fetchJSON(url, options) {
        options = options || {};
        var method = (options.method || 'GET').toUpperCase();
        var headers = options.headers || {};
        headers['X-Requested-With'] = 'XMLHttpRequest';

        if (method !== 'GET') {
            headers['X-CSRFToken'] = getCSRFToken();
            if (!options.body || typeof options.body === 'string') {
                headers['Content-Type'] = 'application/json';
            }
        }

        return fetch(url, {
            method: method,
            headers: headers,
            body: options.body,
            credentials: 'same-origin'
        }).then(function(resp) {
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            var ct = resp.headers.get('content-type') || '';
            if (ct.includes('application/json')) return resp.json();
            return resp.text();
        });
    }

    // ═══════════════════════════════════════════════════════════════════
    // DEBOUNCE
    // ═══════════════════════════════════════════════════════════════════
    function debounce(fn, ms) {
        var timer;
        return function() {
            var ctx = this, args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function() { fn.apply(ctx, args); }, ms);
        };
    }

    // ═══════════════════════════════════════════════════════════════════
    // LIVE SEARCH (AJAX filtering for tables)
    // ═══════════════════════════════════════════════════════════════════
    function initLiveSearch(config) {
        /**
         * config: {
         *   searchInput: '#searchInput',     // selector for text input
         *   statusSelect: '#statusSelect',   // selector for status dropdown (optional)
         *   dateFrom: '#dateFrom',           // selector for date from (optional)
         *   dateTo: '#dateTo',               // selector for date to (optional)
         *   targetContainer: '#tableBody',   // where to inject HTML response
         *   url: '/office/applications/',     // base URL for AJAX
         *   extraParams: {},                  // additional GET params
         *   onBeforeLoad: null,               // callback before AJAX
         *   onAfterLoad: null,                // callback after AJAX
         * }
         */
        var searchEl = config.searchInput ? document.querySelector(config.searchInput) : null;
        var statusEl = config.statusSelect ? document.querySelector(config.statusSelect) : null;
        var dateFromEl = config.dateFrom ? document.querySelector(config.dateFrom) : null;
        var dateToEl = config.dateTo ? document.querySelector(config.dateTo) : null;
        var target = document.querySelector(config.targetContainer);

        if (!target) return;

        function doSearch() {
            var params = new URLSearchParams(config.extraParams || {});
            if (searchEl && searchEl.value.trim()) params.set('q', searchEl.value.trim());
            if (statusEl && statusEl.value) params.set('status', statusEl.value);
            if (dateFromEl && dateFromEl.value) params.set('date_from', dateFromEl.value);
            if (dateToEl && dateToEl.value) params.set('date_to', dateToEl.value);

            var url = config.url + '?' + params.toString();
            if (config.onBeforeLoad) config.onBeforeLoad();

            fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            }).then(function(resp) { return resp.text(); })
              .then(function(html) {
                  target.innerHTML = html;
                  if (config.onAfterLoad) config.onAfterLoad();
                  // Re-init bulk checkboxes in new content
                  if (window.DFS && window.DFS._bulkManager) {
                      window.DFS._bulkManager.rebind();
                  }
              })
              .catch(function(err) {
                  showToast('Failed to load data: ' + err.message, 'error');
              });
        }

        var debouncedSearch = debounce(doSearch, 350);

        if (searchEl) {
            searchEl.addEventListener('input', debouncedSearch);
            searchEl.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') { searchEl.value = ''; doSearch(); }
            });
        }
        if (statusEl) statusEl.addEventListener('change', doSearch);
        if (dateFromEl) dateFromEl.addEventListener('change', doSearch);
        if (dateToEl) dateToEl.addEventListener('change', doSearch);

        return { refresh: doSearch };
    }

    // ═══════════════════════════════════════════════════════════════════
    // BULK ACTION MANAGER
    // ═══════════════════════════════════════════════════════════════════
    function BulkActionManager(config) {
        /**
         * config: {
         *   tableSelector: 'table.bulk-table',
         *   checkboxName: 'app_ids',
         *   toolbarSelector: '#bulkToolbar',
         *   countSelector: '#bulkCount',
         *   selectAllSelector: '#selectAll',
         *   actionUrl: '/office/applications/bulk-action/',
         *   onSelectionChange: null,  // callback(selectedIds)
         * }
         */
        this.config = config;
        this.selectedIds = new Set();
        this.init();
    }

    BulkActionManager.prototype.init = function() {
        this.toolbar = document.querySelector(this.config.toolbarSelector);
        this.countEl = document.querySelector(this.config.countSelector);
        this.rebind();
    };

    BulkActionManager.prototype.rebind = function() {
        var self = this;
        // Select-all checkbox
        var selectAll = document.querySelector(this.config.selectAllSelector);
        if (selectAll) {
            selectAll.onchange = function() {
                var cbs = document.querySelectorAll('input[name="' + self.config.checkboxName + '"]');
                cbs.forEach(function(cb) {
                    cb.checked = selectAll.checked;
                    if (selectAll.checked) self.selectedIds.add(cb.value);
                    else self.selectedIds.delete(cb.value);
                });
                self.updateToolbar();
            };
        }
        // Individual checkboxes
        document.querySelectorAll('input[name="' + this.config.checkboxName + '"]').forEach(function(cb) {
            cb.onchange = function() {
                if (cb.checked) self.selectedIds.add(cb.value);
                else self.selectedIds.delete(cb.value);
                // Update select-all state
                if (selectAll) {
                    var total = document.querySelectorAll('input[name="' + self.config.checkboxName + '"]').length;
                    selectAll.checked = self.selectedIds.size === total && total > 0;
                    selectAll.indeterminate = self.selectedIds.size > 0 && self.selectedIds.size < total;
                }
                self.updateToolbar();
            };
        });
    };

    BulkActionManager.prototype.updateToolbar = function() {
        if (this.toolbar) {
            if (this.selectedIds.size > 0) {
                this.toolbar.classList.add('show');
                this.toolbar.classList.remove('d-none');
            } else {
                this.toolbar.classList.remove('show');
                this.toolbar.classList.add('d-none');
            }
        }
        if (this.countEl) {
            this.countEl.textContent = this.selectedIds.size;
        }
        if (this.config.onSelectionChange) {
            this.config.onSelectionChange(Array.from(this.selectedIds));
        }
    };

    BulkActionManager.prototype.getSelectedIds = function() {
        return Array.from(this.selectedIds);
    };

    BulkActionManager.prototype.clearSelection = function() {
        this.selectedIds.clear();
        document.querySelectorAll('input[name="' + this.config.checkboxName + '"]').forEach(function(cb) {
            cb.checked = false;
        });
        var selectAll = document.querySelector(this.config.selectAllSelector);
        if (selectAll) { selectAll.checked = false; selectAll.indeterminate = false; }
        this.updateToolbar();
    };

    BulkActionManager.prototype.executeAction = function(action, extraData) {
        var self = this;
        var ids = this.getSelectedIds();
        if (ids.length === 0) {
            showToast('Please select at least one item.', 'warning');
            return Promise.reject('No items selected');
        }

        var data = { action: action, app_ids: ids };
        if (extraData) Object.assign(data, extraData);

        if (typeof showLoadingModal === 'function') showLoadingModal('Processing ' + ids.length + ' items...');

        return fetchJSON(this.config.actionUrl, {
            method: 'POST',
            body: JSON.stringify(data)
        }).then(function(result) {
            if (typeof hideLoadingModal === 'function') hideLoadingModal();
            if (result.success !== undefined) {
                var msg = result.message || (result.success + ' item(s) processed successfully.');
                showToast(msg, 'success');
                if (result.errors && result.errors.length) {
                    result.errors.forEach(function(e) { showToast(e, 'warning', 8000); });
                }
            }
            self.clearSelection();
            return result;
        }).catch(function(err) {
            if (typeof hideLoadingModal === 'function') hideLoadingModal();
            showToast('Action failed: ' + err.message, 'error');
            throw err;
        });
    };

    // ═══════════════════════════════════════════════════════════════════
    // CSV EXPORT
    // ═══════════════════════════════════════════════════════════════════
    function exportTableCSV(tableSelector, filename) {
        var table = document.querySelector(tableSelector);
        if (!table) { showToast('No table found to export.', 'warning'); return; }

        var rows = [];
        // Header row
        var headerCells = table.querySelectorAll('thead th');
        var headers = [];
        var skipCols = new Set(); // Skip checkbox and action columns
        headerCells.forEach(function(th, idx) {
            if (th.querySelector('input[type="checkbox"]') || th.classList.contains('col-actions')) {
                skipCols.add(idx);
                return;
            }
            headers.push('"' + (th.textContent || '').trim().replace(/"/g, '""') + '"');
        });
        rows.push(headers.join(','));

        // Data rows
        table.querySelectorAll('tbody tr').forEach(function(tr) {
            var cells = [];
            tr.querySelectorAll('td').forEach(function(td, idx) {
                if (skipCols.has(idx)) return;
                var text = (td.textContent || '').trim().replace(/\s+/g, ' ').replace(/"/g, '""');
                cells.push('"' + text + '"');
            });
            if (cells.length) rows.push(cells.join(','));
        });

        var csv = rows.join('\n');
        var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        var link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = (filename || 'export') + '.csv';
        link.click();
        URL.revokeObjectURL(link.href);
        showToast('CSV exported successfully.', 'success', 3000);
    }

    // Server-side CSV export
    function exportServerCSV(url) {
        window.location.href = url;
    }

    // ═══════════════════════════════════════════════════════════════════
    // KEYBOARD SHORTCUTS
    // ═══════════════════════════════════════════════════════════════════
    var shortcuts = {};

    function registerShortcut(key, callback, description) {
        shortcuts[key.toLowerCase()] = { callback: callback, description: description || key };
    }

    function initKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            // Don't trigger in text inputs (unless it's Escape)
            var tag = (e.target.tagName || '').toLowerCase();
            var isInput = tag === 'input' || tag === 'textarea' || tag === 'select';

            if (e.key === 'Escape') {
                // Close any open modals
                document.querySelectorAll('.modal.show').forEach(function(m) {
                    var inst = bootstrap.Modal.getInstance(m);
                    if (inst) inst.hide();
                });
                // Clear bulk selection
                if (window.DFS && window.DFS._bulkManager) {
                    window.DFS._bulkManager.clearSelection();
                }
                // Blur search input
                if (document.activeElement) document.activeElement.blur();
                return;
            }

            if (isInput) return;

            var key = '';
            if (e.ctrlKey || e.metaKey) key += 'ctrl+';
            if (e.shiftKey) key += 'shift+';
            if (e.altKey) key += 'alt+';
            key += e.key.toLowerCase();

            var shortcut = shortcuts[key];
            if (shortcut) {
                e.preventDefault();
                shortcut.callback(e);
            }
        });

        // Default shortcuts
        registerShortcut('ctrl+k', function() {
            var search = document.querySelector('#searchInput, [data-shortcut="search"]');
            if (search) { search.focus(); search.select(); }
        }, 'Focus search');

        registerShortcut('ctrl+shift+a', function() {
            var selectAll = document.querySelector('#selectAll');
            if (selectAll) { selectAll.checked = !selectAll.checked; selectAll.dispatchEvent(new Event('change')); }
        }, 'Select/deselect all');

        registerShortcut('ctrl+shift+e', function() {
            var exportBtn = document.querySelector('[data-action="export-csv"]');
            if (exportBtn) exportBtn.click();
        }, 'Export CSV');
    }

    // ═══════════════════════════════════════════════════════════════════
    // NOTIFICATION POLLING
    // ═══════════════════════════════════════════════════════════════════
    function initNotificationPolling(url, interval) {
        if (!url) return;
        interval = interval || 60000;

        function poll() {
            fetchJSON(url).then(function(data) {
                if (data && data.count !== undefined) {
                    // Update all notification badges
                    document.querySelectorAll('[data-notification-badge]').forEach(function(badge) {
                        if (data.count > 0) {
                            badge.textContent = data.count > 99 ? '99+' : data.count;
                            badge.style.display = '';
                        } else {
                            badge.style.display = 'none';
                        }
                    });
                }
            }).catch(function() { /* silently fail */ });
        }

        setInterval(poll, interval);
        // Also poll once on load after a short delay
        setTimeout(poll, 3000);
    }

    // ═══════════════════════════════════════════════════════════════════
    // AUTO-INIT ON DOM READY
    // ═══════════════════════════════════════════════════════════════════
    document.addEventListener('DOMContentLoaded', function() {
        // Convert Django messages to toasts
        setTimeout(convertMessagesToToasts, 300);

        // Init keyboard shortcuts
        initKeyboardShortcuts();
    });

    // ═══════════════════════════════════════════════════════════════════
    // PUBLIC API
    // ═══════════════════════════════════════════════════════════════════
    window.DFS = {
        showToast: showToast,
        fetchJSON: fetchJSON,
        debounce: debounce,
        initLiveSearch: initLiveSearch,
        BulkActionManager: BulkActionManager,
        exportTableCSV: exportTableCSV,
        exportServerCSV: exportServerCSV,
        registerShortcut: registerShortcut,
        initNotificationPolling: initNotificationPolling,
        getCSRFToken: getCSRFToken,
        _bulkManager: null  // set by page-level init
    };

})(window);
