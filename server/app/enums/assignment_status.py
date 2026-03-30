from enum import Enum

# Allowed states for a daily assignment
class AssignmentStatus(Enum):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    COMPLETED = 'completed'
    SKIPPED = 'skipped'