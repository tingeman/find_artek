// File upload progress functionality
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('pdf-upload');
    const form = fileInput ? fileInput.closest('form') : null;
    
    if (!fileInput || !form) return;

    // Upload limit per file in MB, rendered by the form from settings.MAX_UPLOAD_SIZE_MB.
    // Without the attribute the browser doesn't check the size; the server still does.
    const maxSizeMb = parseFloat(fileInput.dataset.maxSizeMb);
    const maxSizeBytes = maxSizeMb > 0 ? maxSizeMb * 1024 * 1024 : null;
    
    // Create progress elements
    const progressContainer = document.createElement('div');
    progressContainer.className = 'upload-progress-container';
    progressContainer.style.display = 'none';
    progressContainer.innerHTML = `
        <div class="upload-progress-bar">
            <div class="upload-progress-fill" style="width: 0%"></div>
        </div>
        <div class="upload-progress-text">0%</div>
    `;
    
    // Insert progress container after file input
    fileInput.parentNode.insertBefore(progressContainer, fileInput.nextSibling);
    
    // File selection handler
    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            // Validate file
            if (maxSizeBytes !== null && file.size > maxSizeBytes) {
                alert('File size cannot exceed ' + maxSizeMb + ' MB');
                fileInput.value = '';
                return;
            }
            
            if (!file.name.toLowerCase().endsWith('.pdf')) {
                alert('Only PDF files are allowed');
                fileInput.value = '';
                return;
            }
            
            // Show file info
            const fileInfo = document.createElement('div');
            fileInfo.className = 'file-info';
            fileInfo.innerHTML = `
                <strong>Selected:</strong> ${file.name} 
                (${(file.size / (1024 * 1024)).toFixed(2)} MB)
            `;
            
            // Remove existing file info
            const existingInfo = fileInput.parentNode.querySelector('.file-info');
            if (existingInfo) {
                existingInfo.remove();
            }
            
            fileInput.parentNode.insertBefore(fileInfo, progressContainer);
        }
    });
    
    // Form submission with progress
    form.addEventListener('submit', function(e) {
        const file = fileInput.files[0];
        if (!file) return; // No file selected, proceed normally
        
        e.preventDefault();
        
        const formData = new FormData(form);
        progressContainer.style.display = 'block';
        
        const xhr = new XMLHttpRequest();
        
        // Upload progress
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                const progressFill = progressContainer.querySelector('.upload-progress-fill');
                const progressText = progressContainer.querySelector('.upload-progress-text');
                
                progressFill.style.width = percentComplete + '%';
                progressText.textContent = Math.round(percentComplete) + '%';
            }
        });
        
        // Upload complete
        xhr.addEventListener('load', function() {
            // The server redirected (person workflow or review step): go there in the browser.
            // Copying that page into this one left the address bar on the form URL, so forms
            // without an action on the next page posted back to the form (found 2026-11-20).
            if (xhr.status === 200 && xhr.responseURL &&
                    xhr.responseURL.split('#')[0] !== new URL(form.action, window.location.href).href) {
                window.location.assign(xhr.responseURL);
                return;
            }
            if (xhr.status === 200) {
                // Parse response and redirect if needed
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.success && response.redirect) {
                        window.location.href = response.redirect;
                    } else {
                        // Handle form errors
                        document.body.innerHTML = xhr.responseText;
                    }
                } catch (e) {
                    // If not JSON, assume it's a redirect or HTML response
                    document.body.innerHTML = xhr.responseText;
                }
            } else {
                alert('Upload failed. Please try again.');
                progressContainer.style.display = 'none';
            }
        });
        
        // Upload error
        xhr.addEventListener('error', function() {
            alert('Upload failed. Please try again.');
            progressContainer.style.display = 'none';
        });
        
        xhr.open('POST', form.action);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        
        // Include CSRF token
        const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfToken) {
            xhr.setRequestHeader('X-CSRFToken', csrfToken.value);
        }
        
        xhr.send(formData);
    });
});
