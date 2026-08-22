"""Tenant isolation at the database level.

Postgres Row-Level Security policies (see `accounts/migrations/0002_enable_rls.py`) scope
every company-owned table by a session variable, `app.current_company_id`. This module is
what sets that variable, so a query can only ever return rows belonging to the caller's
company — even if application code forgets a filter or an endpoint is written carelessly.

Why this runs in DRF's `initial()` rather than in middleware: DRF authenticates lazily,
inside the view, so `request.user` is still anonymous while middleware runs. `ATOMIC_REQUESTS`
also wraps the view — and only the view — in a transaction, and `SET LOCAL` is scoped to the
surrounding transaction, so a value set in middleware would apply to the wrong transaction
and be discarded before any query ran.
"""

from django.db import connection
from rest_framework.viewsets import GenericViewSet


def set_current_company(company_id):
    """Scope the current transaction to one company.

    `set_config(..., is_local => true)` is the function form of `SET LOCAL`: the value
    lasts until the end of the transaction, so it cannot leak into the next request served
    by the same pooled connection.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.current_company_id', %s, true)",
            [str(company_id) if company_id is not None else ""],
        )


class TenantScopedViewSetMixin:
    """Applies the caller's company scope before the view runs any query."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        set_current_company(getattr(request.user, "company_id", None))


class TenantViewSet(TenantScopedViewSetMixin, GenericViewSet):
    """Base for every viewset serving company-owned data."""
