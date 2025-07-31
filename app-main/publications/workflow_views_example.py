"""
Example view integration with the multi-step person disambiguation workflow.
This shows how to modify your existing views to use the workflow system.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import Publication
from .enhanced_forms import WorkflowAddEditReportForm, WorkflowAddEditReportFinalSaveForm


@login_required
def add_publication_with_workflow(request):
    """
    Example view showing how to integrate the workflow with publication creation.
    
    This replaces your existing AddEditReportView.as_view() for the workflow version.
    """
    
    if request.method == 'POST':
        form = WorkflowAddEditReportForm(request.POST, request.FILES, request=request)
        
        if form.is_valid():
            # Check if form needs to redirect to workflow
            if form.has_workflow_redirect():
                return form.get_workflow_redirect()
            
            # Form is valid and no workflow needed - proceed with save
            publication = form.save(commit=False)
            publication.created_by = request.user
            publication.modified_by = request.user
            publication.save()
            form.save_m2m()  # Save many-to-many relationships
            
            messages.success(request, 'Publication saved successfully!')
            return redirect('publications:report', pk=publication.pk)
    else:
        form = WorkflowAddEditReportForm(request=request)
    
    context = {
        'form': form,
        'title': 'Add Publication',
        'action': 'add'
    }
    
    return render(request, 'publications/add_edit_report.html', context)


@login_required
def edit_publication_with_workflow(request, pk):
    """
    Example view showing how to integrate the workflow with publication editing.
    """
    publication = get_object_or_404(Publication, pk=pk)
    
    if request.method == 'POST':
        form = WorkflowAddEditReportForm(
            request.POST, request.FILES, 
            instance=publication, 
            request=request
        )
        
        if form.is_valid():
            # Check if form needs to redirect to workflow
            if form.has_workflow_redirect():
                return form.get_workflow_redirect()
            
            # Form is valid and no workflow needed - proceed with save
            publication = form.save(commit=False)
            publication.modified_by = request.user
            publication.save()
            form.save_m2m()
            
            messages.success(request, 'Publication updated successfully!')
            return redirect('publications:report', pk=publication.pk)
    else:
        form = WorkflowAddEditReportForm(instance=publication, request=request)
    
    context = {
        'form': form,
        'publication': publication,
        'title': 'Edit Publication',
        'action': 'edit'
    }
    
    return render(request, 'publications/add_edit_report.html', context)


@login_required
def finalize_publication_with_workflow(request, pk=None):
    """
    Example view for final save with automatic person creation.
    This corresponds to your publication_final_save and edit_report_final_save URLs.
    """
    publication = None
    if pk:
        publication = get_object_or_404(Publication, pk=pk)
    
    if request.method == 'POST':
        form = WorkflowAddEditReportFinalSaveForm(
            request.POST, request.FILES,
            instance=publication,
            request=request
        )
        
        if form.is_valid():
            # This form handles person creation automatically
            publication = form.save(commit=False)
            
            if not publication.pk:
                publication.created_by = request.user
            publication.modified_by = request.user
            publication.save()
            form.save_m2m()
            
            messages.success(request, 'Publication finalized successfully!')
            return redirect('publications:report', pk=publication.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # This shouldn't happen for final save, but handle gracefully
        if publication:
            form = WorkflowAddEditReportFinalSaveForm(instance=publication, request=request)
        else:
            form = WorkflowAddEditReportFinalSaveForm(request=request)
    
    context = {
        'form': form,
        'publication': publication,
        'title': 'Finalize Publication',
        'action': 'finalize'
    }
    
    return render(request, 'publications/add_edit_report_final.html', context)


# Integration guide for existing views:
"""
To integrate the workflow system with your existing views, you need to:

1. Replace your form class:
   OLD: form = AddEditReportForm(...)
   NEW: form = WorkflowAddEditReportForm(..., request=request)

2. Add workflow check after form.is_valid():
   if form.is_valid():
       if form.has_workflow_redirect():
           return form.get_workflow_redirect()
       # ... continue with normal save logic

3. For final save forms, use:
   form = WorkflowAddEditReportFinalSaveForm(..., request=request)
   # This will automatically handle person creation

4. Update your URLs to include workflow endpoints:
   path("workflow/person/disambiguate/", views.disambiguate_person_step, name="disambiguate_person_step"),
   path("workflow/person/complete/", views.complete_person_workflow, name="complete_person_workflow"),

5. Make sure your views import the workflow functions:
   from .person_workflow import disambiguate_person_step, complete_person_workflow

Example URL patterns for your existing views:
   path('add/report/', add_publication_with_workflow, name='add_publication'),
   path('add/report/finalize/', finalize_publication_with_workflow, name='publication_final_save'),
   path('report/<int:pk>/edit/', edit_publication_with_workflow, name='edit_report'),
   path('report/<int:pk>/edit/finalize/', finalize_publication_with_workflow, name='edit_report_final_save'),
"""
