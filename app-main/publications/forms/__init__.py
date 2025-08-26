"""
Forms package for the publications app.
"""

# Import and re-export all form classes
from .base import (
    LoginForm
)
from .person import (
    AddPersonForm, PersonHeavySelect2TagWidget,
    AuthorSelectForm, SupervisorSelectForm, EditorSelectForm, PersonSelectForm
)
from .publication import (
    AddEditReportForm, AddEditReportFinalSaveForm, PublicationForm,
    ChangeReportNumberForm, UploadAppendixForm, DeleteReportForm
)
from .feature import (
    AddFeatureByCoordinatesForm,
    AddFeatureByMap
)
# from .mixins import (
#     PersonWorkflowMixin, 
#     clean_authors_with_workflow, 
#     clean_supervisors_with_workflow, 
#     clean_editors_with_workflow,
#     WorkflowAddEditReportForm, 
#     WorkflowAddEditReportFinalSaveForm
# )
