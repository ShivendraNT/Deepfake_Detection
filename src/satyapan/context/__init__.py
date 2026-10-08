"""Leader-owned context layer that runs BEFORE the (frozen) ask extractor. See ADR-021."""

from satyapan.context.boilerplate import CONTEXT_VERSION, ContextResult, Removed, strip_context

__all__ = ["CONTEXT_VERSION", "ContextResult", "Removed", "strip_context"]
