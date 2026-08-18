"""deskill.core — pure-Python @skills protocol implementation (no CLI/MCP imports)."""
from .autotrigger import (
    ExpandedTrigger, TriggerEntry, add_trigger_line, expand_local_triggers,
    has_trigger_line, parse_triggers, remove_trigger_line,
)
from .cap import MAX_COLLECTION_SKILLS, CollectionTooLargeError, Suggestion
from .ids import (
    GhParts, Reference, disk_path, gh_parts, is_cloud, is_gh, is_local_only,
    normalize_id, parse_reference, reference_spelling,
)
from .residency import build_autotrigger_index, estimate_tokens
from .resolve import Options, Resolved, atskills_root, resolve
from .save import SaveResult, save
from .skillmd import Skill, parse_skill_md, require_trigger_fields

__all__ = [
    'ExpandedTrigger', 'TriggerEntry', 'add_trigger_line', 'expand_local_triggers',
    'has_trigger_line', 'parse_triggers', 'remove_trigger_line',
    'MAX_COLLECTION_SKILLS', 'CollectionTooLargeError', 'Suggestion',
    'GhParts', 'Reference', 'disk_path', 'gh_parts', 'is_cloud', 'is_gh',
    'is_local_only', 'normalize_id', 'parse_reference', 'reference_spelling',
    'build_autotrigger_index', 'estimate_tokens',
    'Options', 'Resolved', 'atskills_root', 'resolve',
    'SaveResult', 'save',
    'Skill', 'parse_skill_md', 'require_trigger_fields',
]
