"""dovera — universal document verification against project checklists."""

from dovera.pipeline import Dovers
from dovera.checklists import Checklist, ChecklistRegistry, Requirement
from dovera.checking.results import CheckResult, Summary, Verdict

__version__ = "2.0.0"
__all__ = ["Dovers", "Checklist", "ChecklistRegistry", "Requirement",
           "CheckResult", "__version__"]
