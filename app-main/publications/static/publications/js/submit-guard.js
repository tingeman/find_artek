// Submit guard for upload forms (report form, appendix upload).
//
// A form with the attribute data-submit-guard is submitted once: the first submit disables
// its submit buttons and shows a spinner with the attribute's text (default "Uploading and
// processing…"); further submits are blocked until the page is shown again (back button,
// bfcache: pageshow) or the upload script unlocks the form after an error.
// file-upload.js (report form with a PDF) updates the text with the upload progress through
// window.submitGuard.setText and unlocks the form on an error.
//
// The listener is on the document in the capture phase, so it runs before the form's own
// submit listeners (file-upload.js) and a second submit never reaches them. The submit
// buttons of guarded forms must not carry a name: a disabled button is not sent.
(function () {
    'use strict';

    const DEFAULT_TEXT = 'Uploading and processing…';

    function buttons(form) {
        return form.querySelectorAll('button[type="submit"], input[type="submit"]');
    }

    function statusElement(form) {
        let status = form.querySelector('.submit-guard-status');
        if (!status) {
            status = document.createElement('div');
            status.className = 'submit-guard-status';
            status.setAttribute('role', 'status');
            status.setAttribute('aria-live', 'polite');
            status.style.display = 'none';
            status.style.marginTop = '10px';
            status.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> ' +
                '<span class="submit-guard-text"></span>';
            const all = buttons(form);
            const last = all[all.length - 1];
            (last ? last.parentNode : form).appendChild(status);
        }
        return status;
    }

    function setText(form, text) {
        statusElement(form).querySelector('.submit-guard-text').textContent = text;
    }

    function lock(form, text) {
        form.dataset.submitting = 'true';
        buttons(form).forEach(function (button) { button.disabled = true; });
        setText(form, text || form.dataset.submitGuard || DEFAULT_TEXT);
        statusElement(form).style.display = 'block';
    }

    function unlock(form) {
        delete form.dataset.submitting;
        buttons(form).forEach(function (button) { button.disabled = false; });
        const status = form.querySelector('.submit-guard-status');
        if (status) status.style.display = 'none';
    }

    document.addEventListener('submit', function (event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || !form.hasAttribute('data-submit-guard')) return;
        if (form.dataset.submitting) {
            event.preventDefault();
            event.stopImmediatePropagation();
            return;
        }
        lock(form);
    }, true);

    // Back to the page (bfcache) or a reload: the form can be submitted again.
    window.addEventListener('pageshow', function () {
        document.querySelectorAll('form[data-submit-guard]').forEach(unlock);
    });

    window.submitGuard = { lock: lock, unlock: unlock, setText: setText };
})();
