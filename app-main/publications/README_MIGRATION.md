# Person Disambiguation Code Consolidation

## Summary of Changes

We have created a plan and implementation for consolidating the redundant person disambiguation code to use the cleaner implementation in `person_disambiguation.py`. This addresses the problem of redundancy in the person disambiguation workflow across multiple files.

## Files Created

1. **`/publications/forms/publication_new_forms.py`**
   - Contains new form classes using the improved `PersonDisambiguationMixin`
   - `DisambiguationWorkflowAddEditReportForm` and `DisambiguationWorkflowAddEditReportFinalSaveForm`

2. **`/publications/urls_updated.py`**
   - Updated URLs configuration using class-based views from `person_disambiguation.py`
   - Replaced function-based views with `DisambiguatePersonStepView` and `CompletePersonWorkflowView`

3. **`/publications/views_updated.py`**
   - Updated view code using the new form classes
   - Fixed imports to refer to the improved implementation

4. **`/publications/migration_plan.md`**
   - Detailed plan for migrating to the new implementation
   - Includes current situation analysis, migration steps, and risk assessment

5. **`/publications/tests/test_migration_validation.py`**
   - Test cases to validate the new implementation
   - Tests form initialization, workflow redirects, and workflow completion

## Next Steps to Complete Migration

1. **Run the validation tests**:
   ```bash
   cd /workspace/app-main
   python manage.py test publications.tests.test_migration_validation
   ```

2. **Update the actual files** after successful testing:

   a. Update `publication.py` by adding the new form classes:
   ```python
   class DisambiguationWorkflowAddEditReportForm(PersonDisambiguationMixin, AddEditReportForm):
       """
       Enhanced AddEditReportForm with person disambiguation workflow.
       Uses the improved PersonDisambiguationMixin from workflows module.
       """
       
       def clean(self):
           """Process all fields at once to properly queue multiple workflows"""
           cleaned_data = super().clean()
           
           # Skip if no service
           if not hasattr(self, 'person_service') or not self.person_service:
               return cleaned_data
           
           # Start workflows for both fields at once
           workflow_redirect = self.start_disambiguation_workflow(['authors', 'supervisors'])
           if workflow_redirect:
               self._workflow_redirect = workflow_redirect
           
           return cleaned_data


   class DisambiguationWorkflowAddEditReportFinalSaveForm(PersonDisambiguationMixin, AddEditReportFinalSaveForm):
       """
       Enhanced final save form with workflow support using the improved PersonDisambiguationMixin.
       """
       
       def clean(self):
           """Process person fields with disambiguation workflow support"""
           cleaned_data = super().clean()
           
           # Skip if no service
           if not hasattr(self, 'person_service') or not self.person_service:
               return cleaned_data
           
           # Check if any fields still need disambiguation
           workflow_redirect = self.start_disambiguation_workflow(['authors', 'supervisors'])
           if workflow_redirect:
               self._workflow_redirect = workflow_redirect
           
           return cleaned_data
   ```

   b. Update `urls.py` by replacing the imports:
   ```python
   # Replace this:
   from publications.workflows.person import disambiguate_person_step, complete_person_workflow
   
   # With this:
   from publications.workflows.person_disambiguation import DisambiguatePersonStepView, CompletePersonWorkflowView
   
   # And update the URL patterns:
   path("workflow/person/disambiguate/", DisambiguatePersonStepView.as_view(), name="disambiguate_person_step"),
   path("workflow/person/complete/", CompletePersonWorkflowView.as_view(), name="complete_person_workflow"),
   ```

   c. Update `views.py` by replacing the form class references:
   ```python
   # Replace this:
   from publications.forms.mixins import WorkflowAddEditReportForm, WorkflowAddEditReportFinalSaveForm
   
   # With this:
   from publications.forms.publication import (
       DisambiguationWorkflowAddEditReportForm, 
       DisambiguationWorkflowAddEditReportFinalSaveForm
   )
   
   # And update the form_class methods:
   def get_form_class(self):
       return DisambiguationWorkflowAddEditReportForm
       
   def get_form_class(self):
       return DisambiguationWorkflowAddEditReportFinalSaveForm
   ```

3. **Test the entire application** after making these changes:
   - Test adding new reports with authors and supervisors
   - Test editing existing reports
   - Test the disambiguation workflow with various inputs
   - Verify that all data is saved correctly

4. **Deprecate the old implementation** by adding comments:
   ```python
   # DEPRECATED: This implementation is redundant with PersonDisambiguationMixin in person_disambiguation.py
   # Use the improved implementation instead
   class PersonWorkflowMixin:
       # ...
   ```

5. **Update documentation** to reflect the new implementation

## Expected Benefits

- Cleaner code with better separation of concerns
- Reduced redundancy and maintenance burden
- More robust person matching with confidence scores
- Consistent session management and workflow handling
