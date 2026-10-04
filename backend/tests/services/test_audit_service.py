from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from core.actor import ActorContext
from core.services import audit_service


def test_diff_only_changed_fields_and_decimals_as_strings():
    changes = audit_service.diff(
        {"market_price": Decimal("300.00"), "name": "Bottle", "qty": 4},
        {"market_price": Decimal("320.00"), "name": "Bottle", "qty": 4},
    )
    assert changes == {"market_price": ["300.00", "320.00"]}


def test_diff_redacts_secrets():
    assert audit_service.diff({"password": "a"}, {"password": "b"}) == {"password": ["***", "***"]}


def test_diff_none_to_value():
    assert audit_service.diff({}, {"barcode": "890"}) == {"barcode": [None, "890"]}


def test_nested_secrets_are_redacted_in_diffs():
    changes = audit_service.diff(
        {}, {"account": {"Authorization": "Bearer secret", "items": [{"token": "secret"}]}}
    )
    assert changes == {"account": [None, {"Authorization": "***", "items": [{"token": "***"}]}]}


@pytest.mark.db
def test_audit_rows_cannot_be_updated_or_deleted(dbs):
    audit_service.record(ActorContext.system(), "test.event", "test", 1, "hello")
    dbs.flush()
    for statement in ("UPDATE audit_logs SET summary = 'x'", "DELETE FROM audit_logs"):
        nested = dbs.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            dbs.execute(text(statement))
        nested.rollback()


@pytest.mark.db
def test_record_redacts_password_in_metadata(dbs):
    row = audit_service.record(
        ActorContext.system(), "test.event", "test", 1, "x", metadata={"password": "secret1"}
    )
    dbs.flush()
    assert row.metadata_ == {"password": "***"}
