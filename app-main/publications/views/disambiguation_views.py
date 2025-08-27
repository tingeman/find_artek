import re
import logging

from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

# Import utility functions that we'll need
from publications.views.base_views import BaseView  # adjust import if needed
from publications.services.disambiguation import PersonDisambiguationService
from publications import models

#from publications.utils.person_matching import PersonMatcher

logger = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class DisambiguatePersonStepView(BaseView):
    """
    View for handling a single step in the person disambiguation workflow.

    This class-based view presents the user with options to resolve an ambiguous person name
    (select existing, create new, or skip), processes the user's choice, and advances the workflow.
    It uses PersonDisambiguationService to manage workflow state in the session.
    """
    template_name = 'publications/person_disambiguation_step.html'

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests: Display the disambiguation step for the current ambiguous person.

        - Checks if a workflow is active and a person is pending resolution.
        - Gathers context (matches, clean name, progress info) for the template.
        - Renders the disambiguation step page.
        """
        service = PersonDisambiguationService(request)

        is_active, current_person, redirect_url, error_message = self._get_workflow_state(service)
        if not is_active:
            if error_message:
                messages.error(request, error_message)
            return redirect(redirect_url)

        # Get possible matches for the current ambiguous name
        matches = service.get_matches_for_current_person()
        # Remove any tags from the name for display
        clean_name = service._remove_tags(current_person)
        # Get progress info (step number, total steps, percent)
        step_info = service.get_current_step_info()

        # Prepare context for the template
        context = {
            'current_person_name': current_person,
            'clean_name': clean_name,
            'matches': matches,
            'field_name': service.session['person_disambiguation']['workflows'][service.session['person_disambiguation']['current_index']]['field_name'],
            'step_number': step_info['current_step'],
            'total_steps': step_info['total_steps'],
            'progress_percent': step_info['progress_percent']
        }
        # Add any additional context from BaseView
        context.update(self.get_context_data())
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: Process the user's action for the current ambiguous person.

        - Handles three actions: select_existing, create_new, skip.
        - Updates the workflow state and advances to the next step or completes the workflow.
        - On error, re-renders the page with error messages.
        """
        service = PersonDisambiguationService(request)

        is_active, current_person, redirect_url, error_message = self._get_workflow_state(service)
        if not is_active:
            if error_message:
                messages.error(request, error_message)
            return redirect(redirect_url)

        action = request.POST.get('action')
        logger.debug(f'POST: action={action}, current_person={current_person}')
        # User selects an existing person from the matches
        if action == 'select_existing':
            person_id = request.POST.get('person_id')
            logger.debug(f'POST: select_existing, person_id={person_id}')
            if person_id:
                service.resolve_current_person(person_id)
                # If all persons are resolved, finalize the workflow
                if service.is_workflow_finalized():
                    return redirect('publications:finalize_person_workflow')
                else:
                    return redirect('publications:disambiguate_person_step')
            else:
                messages.error(request, "No person selected.")
        # User chooses to create a new person
        elif action == 'create_new':
            person_name = service._remove_tags(current_person)
            logger.debug(f'POST: create_new, person_name={person_name}')
            try:
                # Mark this name as resolved with a CREATE: marker
                logger.debug(f'POST: About to call service.resolve_current_person with CREATE:{person_name}')
                service.resolve_current_person(f"CREATE:{person_name}")
                logger.debug(f'POST: After resolve_current_person, session={dict(request.session)}')
                messages.success(request, f'Marked new person for creation: {person_name}')
                if service.is_workflow_finalized():
                    logger.debug('POST: Workflow finalized after create_new')
                    return redirect('publications:finalize_person_workflow')
                else:
                    logger.debug('POST: Workflow NOT finalized after create_new, redirecting to next step')
                    return redirect('publications:disambiguate_person_step')
            except Exception as e:
                logger.exception(f"Error creating person: {e}")
                messages.error(request, f"Error creating person: {e}")
        # User chooses to skip this name (not a person or to handle later)
        elif action == 'skip':
            logger.debug(f'POST: skip, current_person={current_person}')
            service.resolve_current_person(f"SKIP:{current_person}")
            if service.is_workflow_finalized():
                return redirect('publications:complete_person_workflow')
            else:
                return redirect('publications:disambiguate_person_step')

        # If we get here, there was an error or no action taken; re-render the page
        logger.debug('POST: No valid action taken or error occurred, re-rendering page')
        return self.get(request, *args, **kwargs)
    
    def _get_workflow_state(self, service):
        """
        Returns a tuple (is_active, current_person, redirect_url or None, error_message or None)
        """
        # Try to advance to next workflow if the current one is complete
        if service.is_workflow_finalized():
            logger.debug("_get_workflow_state: Current workflow is complete, trying to advance")
            service.advance_to_next_workflow()
        
        # Now check if there's an active workflow
        if not service.is_workflow_active():
            logger.debug("_get_workflow_state: No active workflow after advance attempt")
            pd = service.session.get('person_disambiguation', {})
            workflows = pd.get('workflows', [])
            url = workflows[0].get('source_url', 'publications:frontpage') if workflows else 'publications:frontpage'
            return False, None, url, "No active disambiguation workflow."
        
        current_person = service.get_current_person()
        if not current_person:
            logger.debug("_get_workflow_state: No current person in the active workflow")
            pd = service.session.get('person_disambiguation', {})
            workflows = pd.get('workflows', [])
            url = (workflows[pd.get('current_index')].get('source_url', 'publications:frontpage')
                if workflows and pd.get('current_index') is not None else 'publications:frontpage')
            return False, None, url, "No person to disambiguate."
        
        logger.debug(f"_get_workflow_state: Found active workflow with current_person={current_person}")
        return True, current_person, None, None
        

@method_decorator(login_required, name='dispatch')
class FinalizePersonWorkflowView(BaseView):
    """
    View to finalize the person disambiguation workflow.

    This class-based view finalizes the workflow, updates the form data with
    resolved persons, and redirects back to the form or a fallback page.
    """

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests to finalize the workflow and redirect appropriately.
        """
        service = PersonDisambiguationService(request)
        logger.debug("FinalizePersonWorkflowView.get: Starting workflow finalization")

        # Check if workflow is finalized
        if not service.is_workflow_finalized():
            logger.debug("FinalizePersonWorkflowView.get: Current workflow not finalized")
            messages.error(request, "Current disambiguation workflow not finalized.")
            return redirect('publications:disambiguate_person_step')

        # Finalize workflow and get redirect URL
        updated_form_data, redirect_url = service.finalize_workflow()
        logger.debug(f"FinalizePersonWorkflowView.get: finalize_workflow returned redirect_url={redirect_url}")

        if not redirect_url:
            # Fallback to frontpage
            logger.debug("FinalizePersonWorkflowView.get: No redirect URL, redirecting to frontpage")
            messages.error(request, "Error finalizing workflow.")
            return redirect('publications:frontpage')

        if redirect_url == 'publications:disambiguate_person_step':
            logger.debug("FinalizePersonWorkflowView.get: More workflows to process, redirecting to next disambiguation step")
            messages.success(request, "Moving to next disambiguation step.")
            return redirect(redirect_url)

        logger.debug(f"FinalizePersonWorkflowView.get: All workflows finalized, redirecting to {redirect_url}")
        messages.success(request, "Person disambiguation complete.")
        return redirect(redirect_url)
    

@method_decorator(login_required, name='dispatch')
class ClearDisambiguationWorkflowsView(BaseView):
    """
    View endpoint to manually clear all disambiguation workflows
    while preserving original form data.
    
    Access via: /publications/workflow/person/clear/
    """
    
    def get(self, request):
        """Handle GET requests to clear all disambiguation workflows."""
        service = PersonDisambiguationService(request)
        
        # Get session state before clearing
        pd = request.session.get('person_disambiguation', {})
        workflows = pd.get('workflows', [])
        workflow_count = len(workflows)

        # Check for redirect URL
        redirect_url = request.GET.get('redirect')
        if not redirect_url and workflows and workflows[0].get('source_url'):
            redirect_url = workflows[0].get('source_url')

        # Log current state
        logger.debug(f"ClearDisambiguationWorkflowsView: Found {workflow_count} workflows to clear")

        # Use service method to clear workflows (preserving original form data).
        # clear_workflows_only preserves original_form_data so the user can
        # return to the form with their entered values intact.
        service.clear_workflows_only()

        logger.debug("ClearDisambiguationWorkflowsView: Cleared all disambiguation workflows")

        # Add preserve_form_data flag to the redirect URL if present
        if redirect_url:
            separator = '&' if '?' in redirect_url else '?'
            redirect_url = f"{redirect_url}{separator}preserve_form_data=1"
            return redirect(redirect_url)

        # Default redirect to frontpage
        return redirect('publications:frontpage')


@method_decorator(login_required, name='dispatch')
class DisambiguationWorkflowStatusView(BaseView):
    """
    View endpoint to check the status of disambiguation workflows.
    
    Access via: /publications/workflow/person/status/
    
    Returns JSON with workflow status information.
    """
    
    def get(self, request):
        """Handle GET requests to report disambiguation workflow status."""
        service = PersonDisambiguationService(request)
        
        # Get session state
        pd = request.session.get('person_disambiguation', {})
        workflows = pd.get('workflows', [])
        current_index = pd.get('current_index')
        
        # Build status information
        status = {
            'success': True,
            'workflow_count': len(workflows),
            'has_active_workflow': service.is_workflow_active(),
            'current_index': current_index,
            'fields_pending': [],
            'fields_completed': [],
            'original_form_data_present': 'original_form_data' in pd,
        }
        
        # Analyze workflows
        for i, wf in enumerate(workflows):
            field_name = wf.get('field_name', 'unknown')
            pending_count = len(wf.get('pending_persons', []))
            resolved_count = len(wf.get('resolved_persons', {}))
            
            if pending_count > 0:
                status['fields_pending'].append({
                    'field_name': field_name,
                    'workflow_index': i,
                    'pending_count': pending_count,
                    'resolved_count': resolved_count,
                    'completion_percent': int(100 * resolved_count / pending_count) if pending_count > 0 else 0
                })
            else:
                status['fields_completed'].append({
                    'field_name': field_name,
                    'workflow_index': i,
                    'resolved_count': resolved_count
                })
        
        status['session_data'] = pd

        # Return JSON response
        return JsonResponse(status)



# AJAX Functions for Person Disambiguation Workflow
# Based on legacy Django 1.6 implementation

# TODO: Use NameNormalizer instead of separate functions.

# def get_tag(string, tag_name):
#     """Extract tag value from string like '[id:123]' -> 123"""
#     pattern = r'\[' + tag_name + r':([^\]]+)\]'
#     match = re.search(pattern, string)
#     if match:
#         value = match.group(1)
#         if value == '0':
#             return 0
#         elif value == 'ldap':
#             return 'ldap'
#         else:
#             try:
#                 return int(value)
#             except ValueError:
#                 return None
#     return None


# def remove_tags(string):
#     """Remove all tags like '[id:123]' from string"""
#     return re.sub(r'\[[^\]]+\]', '', string).strip()


# def get_person_matches(name_string, exact=True, relaxed=True):
#     """
#     Find person matches in database.
#     Returns (queryset, match_type) tuple.
#     """
#     clean_name = remove_tags(name_string).strip()
    
#     if not clean_name:
#         return (models.Person.objects.none(), None)
    
#     # Try exact match first
#     if exact:
#         exact_matches = models.Person.objects.filter(name__iexact=clean_name)
#         if exact_matches.exists():
#             return (exact_matches, 'db_exact')
    
#     # Try relaxed match (split on common separators)
#     if relaxed:
#         name_parts = re.split(r'[,\s]+', clean_name)
#         if len(name_parts) >= 2:
#             # Try matching first and last name components
#             first_part = name_parts[0].strip()
#             last_part = name_parts[-1].strip()
            
#             relaxed_matches = models.Person.objects.filter(
#                 name__icontains=first_part
#             ).filter(
#                 name__icontains=last_part
#             )
            
#             if relaxed_matches.exists():
#                 return (relaxed_matches, 'db_relaxed')
    
#     return (models.Person.objects.none(), None)

