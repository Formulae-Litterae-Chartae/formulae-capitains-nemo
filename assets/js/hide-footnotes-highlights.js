document.addEventListener('DOMContentLoaded', function () {
    var STORAGE_PREFIX = 'cleanCopy.';

    function render() {
        document.querySelectorAll('.clean-toggle').forEach(function (btn) {
            var hidden = document.body.classList.contains(btn.dataset.toggleClass);
            btn.querySelector('i').className = 'fas ' + (hidden ? 'fa-eye-slash' : 'fa-eye');
            btn.querySelector('.clean-toggle-label').textContent =
                hidden ? btn.dataset.labelShow : btn.dataset.labelHide;
            btn.setAttribute('aria-pressed', hidden ? 'true' : 'false');
        });
    }

    // Restore saved state (default: everything visible)
    ['hide-footnotes', 'hide-highlights'].forEach(function (cls) {
        var saved = null;
        try { saved = localStorage.getItem(STORAGE_PREFIX + cls); } catch (e) {}
        document.body.classList.toggle(cls, saved === 'true');
    });
    render();

    // One delegated handler for all buttons
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.clean-toggle');
        if (!btn) return;
        e.preventDefault();
        var cls = btn.dataset.toggleClass;
        var hidden = document.body.classList.toggle(cls);
        try { localStorage.setItem(STORAGE_PREFIX + cls, hidden); } catch (err) {}
        render();
    });
});