
import os
import tempfile

# === Django imports ===
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required

from django.shortcuts import get_object_or_404, render, redirect
from django.utils.decorators import method_decorator

# === Project-specific imports ===
from publications import models
from publications.forms import UploadAppendixForm
from publications.utils_models import handle_session_appendix_uploads
from publications.views.base_views import BaseView
from publications.utils.register_from_file import xlsx_pubs
from publications.forms.publication import ImportPublicationFileForm

from publications.views.base_views import BaseView, BaseFormView 




class UploadAppendixView(BaseView):
    """
    View for uploading multiple appendix files to a publication.
    Uses session-based batch management for file handling.
    
    Note: For very large files (>100MB), we may need to implement 
    a secondary upload scheme with chunked uploads or direct storage.
    """
    template_name = 'publications/upload_appendix.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        publication_id = self.kwargs['pk']
        
        # Get the publication
        publication = get_object_or_404(models.Publication, id=publication_id)
        context['publication'] = publication
        
        # Import forms here to avoid circular imports
        context['form'] = UploadAppendixForm()
        
        # Get session files for this publication
        session_key = f'appendix_upload_{publication_id}'
        # Note: request is not available in get_context_data, will handle in get method
        context['session_files'] = []
        
        # Get existing appendices
        context['existing_appendices'] = publication.appendices.all()
        
        return context
    
    def get(self, request, **kwargs):
        self.request = request  # Store request for context access
        self.kwargs = kwargs    # Store kwargs for context access
        context = self.get_context_data(**kwargs)
        
        # Add session files here where we have access to request
        publication_id = kwargs['pk']
        session_key = f'appendix_upload_{publication_id}'
        context['session_files'] = request.session.get(session_key, [])
        
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """Handle different POST actions: upload, remove, submit, cancel"""
        publication_id = self.kwargs['pk']
        publication = get_object_or_404(models.Publication, id=publication_id)
        action = request.POST.get('action', 'upload')
        
        if action == 'upload':
            return self.handle_file_upload(request, publication)
        elif action == 'remove':
            return self.handle_file_removal(request, publication)
        elif action == 'submit':
            return self.handle_submit(request, publication)
        elif action == 'cancel':
            return self.handle_cancel(request, publication)
        else:
            return self.get(request, *args, **kwargs)
    
    def handle_file_upload(self, request, publication):
        """Add uploaded files to session storage"""
        
        form = UploadAppendixForm(request.POST, request.FILES)
        
        if form.is_valid():
            files = request.FILES.getlist('appendix_files')
            session_key = f'appendix_upload_{publication.id}'
            session_files = request.session.get(session_key, [])
            
            for uploaded_file in files:
                # Save to temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                try:
                    for chunk in uploaded_file.chunks():
                        temp_file.write(chunk)
                    temp_file.close()
                    
                    # Store file info in session
                    file_info = {
                        'filename': uploaded_file.name,
                        'temp_path': temp_file.name,
                        'size': uploaded_file.size,
                        'content_type': uploaded_file.content_type,
                    }
                    session_files.append(file_info)
                    
                except Exception as e:
                    # Clean up on error
                    try:
                        os.unlink(temp_file.name)
                    except OSError:
                        pass
                    # Add error message
                    messages.error(request, f'Error uploading {uploaded_file.name}: {e}')
            
            # Update session
            request.session[session_key] = session_files
            request.session.modified = True
            
            messages.success(request, f'Successfully uploaded {len(files)} file(s)')
        
        return redirect('publications:upload_appendix', pk=publication.id)
    
    def handle_file_removal(self, request, publication):
        """Remove a file from session storage"""
        
        file_index = int(request.POST.get('file_index', -1))
        session_key = f'appendix_upload_{publication.id}'
        session_files = request.session.get(session_key, [])
        
        if 0 <= file_index < len(session_files):
            file_to_remove = session_files.pop(file_index)
            
            # Clean up temporary file
            temp_path = file_to_remove.get('temp_path')
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
            
            # Update session
            request.session[session_key] = session_files
            request.session.modified = True
            
            messages.success(request, f'Removed {file_to_remove["filename"]}')
        
        return redirect('publications:upload_appendix', pk=publication.id)
    
    def handle_submit(self, request, publication):
        """Commit all session files to the publication"""
        
        try:
            created_files = handle_session_appendix_uploads(request, publication)
            
            if created_files:
                messages.success(
                    request, 
                    f'Successfully attached {len(created_files)} appendix file(s) to publication {publication.number}'
                )
            else:
                messages.info(request, 'No files were uploaded')
                
            # Redirect to publication detail page
            return redirect('publications:report', pk=publication.id)
            
        except Exception as e:
            messages.error(request, f'Error processing files: {e}')
            return redirect('publications:upload_appendix', pk=publication.id)
    
    def handle_cancel(self, request, publication):
        """Cancel upload and clean up session files"""
        
        session_key = f'appendix_upload_{publication.id}'
        session_files = request.session.get(session_key, [])
        
        # Clean up temporary files
        for file_info in session_files:
            temp_path = file_info.get('temp_path')
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
        
        # Clear session
        if session_key in request.session:
            del request.session[session_key]
        
        messages.info(request, 'Upload cancelled')
        
        # Redirect to publication detail page
        return redirect('publications:report', pk=publication.id)




@method_decorator(login_required, name='dispatch')
class AddReportsFromFileUploadView(BaseFormView):
    template_name = "publications/add_reports_from_file_upload.html"
    form_class = ImportPublicationFileForm

    def form_valid(self, form):
        uploaded_file = form.cleaned_data["file"]
        upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        # Call the parsing function
        filemessages = xlsx_pubs(file_path, user=self.request.user)
        for level, msg in filemessages:
            messages.add_message(self.request, level, msg)

        # Redirect back to the same page to show messages
        return redirect("publications:add_reports_from_file_upload")

    def form_invalid(self, form):
        print("🔍 DEBUG: ChangeReportNumberView.form_invalid called")
        print(f"🔍 DEBUG: form.errors={form.errors}")
        print(f"🔍 DEBUG: form.cleaned_data={getattr(form, 'cleaned_data', None)}")
        messages.error(self.request, "Please correct the errors below.")
        context = self.get_context_data(form=form)
        return render(self.request, self.template_name, context)
