"""Adapter protocol for fidelity benchmarking.

Repository-specific adapters belong in tests/fidelity/adapters/.
The core runner operates only on this protocol.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import FidelityCase, ImplementationIdentity, Observation, RenderProfile


@runtime_checkable
class FidelityAdapter(Protocol):
    def identity(self) -> ImplementationIdentity:
        """Return stable identity for this adapter instance."""
        ...

    def observe(self, case: FidelityCase, profile: RenderProfile) -> Observation:
        """Render case under profile and return a full Observation.

        Must never raise for expected failure modes — return an Observation
        with an appropriate ComparisonStatus instead.
        """
        ...
