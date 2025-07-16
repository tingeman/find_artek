// File upload progress functionality
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('pdf-upload');
    const form = fileInput ? fileInput.closest('form') : null;
    
    if (!fileInput || !form) return;
    
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
            if (file.size > 50 * 1024 * 1024) {
                alert('File size cannot exceed 50MB');
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
