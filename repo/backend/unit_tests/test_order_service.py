from threading import Barrier, Thread

from app.extensions import db
from app.repositories.auth_repository import AuthRepository
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.order_repository import OrderRepository
from app.services.order_service import OrderService


def _user_id(username: str) -> str:
    return AuthRepository().get_user_by_username(username).id


def test_duplicate_checkout_key_returns_same_order(file_app):
    with file_app.app_context():
        catalog_repo = CatalogRepository()
        order_service = OrderService(OrderRepository(), catalog_repo)
        dish = catalog_repo.get_dish_by_slug("citrus-tofu-bowl")
        customer_id = _user_id("customer")

        order_service.add_cart_item(customer_id, {"dish_id": dish.id, "quantity": 1, "selected_options": {}})
        first_order = order_service.checkout(customer_id, "dup-key-1")
        second_order = order_service.checkout(customer_id, "dup-key-1")
        refreshed_dish = catalog_repo.get_dish(dish.id)

        assert first_order.id == second_order.id
        assert refreshed_dish.stock_quantity == 7


def test_concurrent_checkout_prevents_oversell(file_app):
    with file_app.app_context():
        catalog_repo = CatalogRepository()
        low_stock_dish = catalog_repo.get_dish_by_slug("citrus-tofu-bowl")
        low_stock_dish.stock_quantity = 1
        db.session.add(low_stock_dish)
        db.session.commit()

        customer_id = _user_id("customer")
        moderator_id = _user_id("moderator")
        OrderService(OrderRepository(), catalog_repo).add_cart_item(
            customer_id, {"dish_id": low_stock_dish.id, "quantity": 1, "selected_options": {}}
        )
        OrderService(OrderRepository(), catalog_repo).add_cart_item(
            moderator_id, {"dish_id": low_stock_dish.id, "quantity": 1, "selected_options": {}}
        )

    barrier = Barrier(2)
    results: list[tuple[str, str]] = []

    def worker(username: str, key: str):
        with file_app.app_context():
            service = OrderService(OrderRepository(), CatalogRepository())
            barrier.wait()
            try:
                order = service.checkout(_user_id(username), key)
                results.append(("ok", order.id))
            except Exception as exc:  # AppError or busy fallback
                results.append(("error", getattr(exc, "code", exc.__class__.__name__)))

    threads = [
        Thread(target=worker, args=("customer", "race-key-1")),
        Thread(target=worker, args=("moderator", "race-key-2")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with file_app.app_context():
        refreshed = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")

    ok_count = sum(1 for status, _ in results if status == "ok")
    assert ok_count == 1
    assert refreshed.stock_quantity == 0
    assert any(
        code in {"inventory_shortage", "checkout_busy", "dish_sold_out"}
        for status, code in results
        if status == "error"
    )
