# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from enum import Enum

# Allowed states for a daily assignment
# Contract: AssignmentStatus defines a typed boundary and should remain behavior-stable.
class AssignmentStatus(Enum):
    DRAFT = 'draft'
    SUPERVISOR_APPROVED = 'supervisor_approved'  # FIX: [UX-10] Supervisor gate between draft and publish.
    PUBLISHED = 'published'
    COMPLETED = 'completed'
    SKIPPED = 'skipped'
