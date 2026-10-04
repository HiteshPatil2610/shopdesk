import pytest

from core.services.audit_view_service import csv_cell


@pytest.mark.parametrize("value", ["=1+1", "+cmd", "-1", "@SUM(1)", "  =1", "\tformula", "\rtext"])
def test_dangerous_csv_cells_are_prefixed(value):
    assert csv_cell(value) == "'" + value


def test_plain_csv_values_are_preserved():
    assert csv_cell("Bottle, steel") == "Bottle, steel"
    assert csv_cell(None) == ""
