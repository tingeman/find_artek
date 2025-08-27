# Person Disambiguation Workflow Migration Plan

This document outlines the plan for migrating from the redundant person disambiguation implementations to using the cleaner implementation in `person_disambiguation.py`.

## Current Situation

Currently, there are multiple implementations of the person disambiguation workflow:

1. **Main implementation** in `/publications/workflows/person_disambiguation.py`:
   - Contains `PersonDisambiguationService`, `PersonDisambiguationMixin`, and the view classes
   - More structured and maintainable approach
   - Cleaner API with better separation of concerns

2. **Redundant implementation** in `/publications/forms/mixins.py`:
   - Contains `PersonWorkflowMixin`, `WorkflowAddEditReportForm`, and `WorkflowAddEditReportFinalSaveForm`
   - Functions like `clean_authors_with_workflow()` and others
   - Different session key names and workflow management

3. **Additional code** in `/publications/workflows/person.py`:
   - Functions like `disambiguate_person_step` and `complete_person_workflow`
   - Contains `PersonWorkflowSession` class with its own session management

## Migration Steps

### 1. Form Classes Migration

- [x] Created new form classes using the newer `PersonDisambiguationMixin`:
  - `DisambiguationWorkflowAddEditReportForm`
  - `DisambiguationWorkflowAddEditReportFinalSaveForm`
  - Located in `/publications/forms/publication_new_forms.py`

### 2. URLs Update

- [x] Created updated URLs configuration in `urls_updated.py`
  - Use class-based views from `person_disambiguation.py` instead of function-based views
  - Changed imports from `person.py` to `person_disambiguation.py`

### 3. Views Update

- [x] Created updated view code in `views_updated.py`
  - Changed form class references to use the new `Disambiguation*` classes
  - Updated imports accordingly

### 4. Testing Strategy

1. **Test form validation and workflow:** 
   - Test the new form classes with various inputs
   - Verify workflow redirects happen as expected

2. **Test workflow completion:**
   - Test the entire disambiguation workflow end-to-end
   - Verify data is correctly stored and updated

3. **Test session data:**
   - Verify session data structure matches expectations
   - Test edge cases like empty fields and multiple fields

### 5. Implementation Migration

1. Move the new files to replace the existing ones:
   - Merge `publication_new_forms.py` content into `publication.py`
   - Update `urls.py` with the content from `urls_updated.py`
   - Update `views.py` with the relevant changes from `views_updated.py`

2. Remove redundant code:
   - Remove the old `WorkflowAddEditReportForm` and `WorkflowAddEditReportFinalSaveForm` from `mixins.py`
   - Mark functions in `person.py` as deprecated, with comments to use `person_disambiguation.py` equivalents

### 6. Long-term Plan

1. **Complete migration:**
   - Once all code is using the new implementation, remove deprecated functions
   - Eventually remove `person.py` workflow code entirely and rely solely on `person_disambiguation.py`

2. **Code cleanup:**
   - Unify field naming conventions
   - Remove redundant utility functions
   - Improve error handling and messaging

## Benefits of Migration

1. **Improved code organization**: Clear separation between service, mixin, and views
2. **Reduced duplication**: One implementation instead of multiple redundant ones
3. **Better maintainability**: More structured code with clearer API
4. **Enhanced functionality**: The newer implementation has additional features like match confidence scoring

## Potential Risks and Mitigations

1. **Session data format changes**:
   - **Risk**: The new implementation uses different session keys and data formats
   - **Mitigation**: Thoroughly test workflow completion and session data handling

2. **Template compatibility**:
   - **Risk**: Templates might expect specific context variables
   - **Mitigation**: Ensure view classes provide consistent context variables

3. **Integration points**:
   - **Risk**: Other code might depend on specific behavior of the old implementation
   - **Mitigation**: Identify all integration points and test them with the new implementation
