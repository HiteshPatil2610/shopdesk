"""BR-7 under real concurrency: two counters sell the LAST unit at the same moment.

This test commits for real (no rolled-back transaction), so conftest runs it after every other
test; the next session wipes the test schema anyway.
"""

import threading
import uuid

import pytest
from sqlalchemy import func, select

from core.db import db
from core.models import Order, Product, User
from tests.conftest import POS_ORIGIN

pytestmark = [pytest.mark.db, pytest.mark.concurrency]


def test_last_unit_sold_once_under_concurrency(test_db, settings, make_token):
    from pos_api import create_app

    app = create_app(settings)
    tag = uuid.uuid4().hex[:6]
    with app.app_context():
        cashiers = [
            User(
                clerk_user_id=f"user_race_{tag}_{i}",
                username=f"race{i}{tag}",
                full_name=f"Racer {i}",
                role="cashier",
            )
            for i in range(2)
        ]
        product = Product(
            code=f"R{tag[:5].upper()}",
            name="Last unit",
            cost_price=100,
            market_price=200,
            selling_price=180,
            quantity=1,
        )
        db.session.add_all([*cashiers, product])
        db.session.commit()
        product_id, code = product.id, product.code
        db.session.remove()

    barrier = threading.Barrier(2)
    results: list[int] = []

    def sell(i: int) -> None:
        token = make_token(sub=f"user_race_{tag}_{i}", role="cashier", azp=POS_ORIGIN)
        client = app.test_client()
        barrier.wait()
        res = client.post(
            "/api/orders/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "idempotency_key": str(uuid.uuid4()),
                "customer_name": f"Customer {i}",
                "discount_applied": False,
                "items": [{"code": code, "qty": 1}],
            },
        )
        results.append(res.status_code)

    threads = [threading.Thread(target=sell, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert sorted(results) == [201, 409]
    with app.app_context():
        assert db.session.get(Product, product_id).quantity == 0
        sold = db.session.scalar(
            select(func.count()).select_from(Order).where(Order.customer_name.like("Customer %"))
        )
        assert sold == 1
        db.session.remove()
