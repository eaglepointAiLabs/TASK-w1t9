import pytest
from threading import Barrier, Thread

from app.extensions import db
from app.repositories.auth_repository import AuthRepository
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.order_repository import OrderRepository
from app.services.errors import AppError
from app.services.order_service import OrderService


def _user_id(username: str) -> str:
    return AuthRepository().get_user_by_username(username).id


def test_add_cart_item_creates_cart_and_item(app):
    with app.app_context():
        catalog_repo = CatalogRepository()
        order_service = OrderService(OrderRepository(), catalog_repo)
        dish = catalog_repo.get_dish_by_slug("citrus-tofu-bowl")
        customer_id = _user_id("customer")

        item, cart = order_service.add_cart_item(customer_id, {"dish_id": dish.id, "quantity": 2, "selected_options": {}})

        assert item.quantity == 2
        assert cart.status == "active"
        assert len(cart.items) >= 1


def test_add_cart_item_rejects_zero_quantity(app):
    with app.app_context():
        catalog_repo = CatalogRepository()
        order_service = OrderService(OrderRepository(), catalog_repo)
        dish = catalog_repo.get_dish_by_slug("citrus-tofu-bowl")
        customer_id = _user_id("customer")

        with pytest.raises(AppError) as exc:
            order_service.add_cart_item(customer_id, {"dish_id": dish.id, "quantity": 0, "selected_options": {}})
        assert exc.value.code == "validation_error"


def test_update_cart_item_changes_quantity(app):
    with app.app_context():
        catalog_repo = CatalogRepository()
        order_service = OrderService(OrderRepository(), catalog_repo)
        dish = catalog_repo.get_dish_by_slug("citrus-tofu-bowl")
        customer_id = _user_id("customer")

        item, cart = order_service.add_cart_item(customer_id, {"dish_id": dish.id, "quantity": 1, "selected_options": {}})
        updated_item, _ = order_service.update_cart_item(customer_id, item.id, {"quantity": 3})

        assert updated_item.quantity == 3


def test_delete_cart_item_removes_from_cart(app):
    with app.app_context():
        catalog_repo = CatalogRepository()
        order_service = OrderService(OrderRepository(), catalog_repo)
        dish = catalog_repo.get_dish_by_slug("citrus-tofu-bowl")
        customer_id = _user_id("customer")

        item, cart = order_service.add_cart_item(customer_id, {"dish_id": dish.id, "quantity": 1, "selected_options": {}})
        updated_cart = order_service.delete_cart_item(customer_id, item.id)

        assert all(i.id != item.id for i in updated_cart.items)


def test_delete_nonexistent_cart_item_returns_404(app):
    with app.app_context():
        catalog_repo = CatalogRepository()
        order_service = OrderService(OrderRepository(), catalog_repo)
        customer_id = _user_id("customer")
        order_service.get_cart(customer_id)

        with pytest.raises(AppError) as exc:
            order_service.delete_cart_item(customer_id, "nonexistent-item-id")
        assert exc.value.code == "not_found"


def test_checkout_rejects_empty_cart(app):
    with app.app_context():
        catalog_repo = CatalogRepository()
        order_service = OrderService(OrderRepository(), catalog_repo)
        moderator_id = _user_id("moderator")

        with pytest.raises(AppError) as exc:
            order_service.checkout(moderator_id, "empty-cart-key")
        assert exc.value.code == "validation_error"


def test_checkout_rejects_missing_checkout_key(app):
    with app.app_context():
        catalog_repo = CatalogRepository()
        order_service = OrderService(OrderRepository(), catalog_repo)
        customer_id = _user_id("customer")

        with pytest.raises(AppError) as exc:
            order_service.checkout(customer_id, "")
        assert exc.value.code == "validation_error"


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


def test_checkout_rejects_sold_out_dish(app):
    with app.app_context():
        catalog_repo = CatalogRepository()
        order_service = OrderService(OrderRepository(), catalog_repo)
        dish = catalog_repo.get_dish_by_slug("citrus-tofu-bowl")
        customer_id = _user_id("customer")

        order_service.add_cart_item(customer_id, {"dish_id": dish.id, "quantity": 1, "selected_options": {}})

        dish.is_sold_out = True
        db.session.add(dish)
        db.session.commit()

        with pytest.raises(AppError) as exc:
            order_service.checkout(customer_id, "sold-out-key")
        assert exc.value.code == "dish_sold_out"


def test_get_order_returns_order_for_owner(app):
    with app.app_context():
        catalog_repo = CatalogRepository()
        order_service = OrderService(OrderRepository(), catalog_repo)
        dish = catalog_repo.get_dish_by_slug("citrus-tofu-bowl")
        customer_id = _user_id("customer")

        order_service.add_cart_item(customer_id, {"dish_id": dish.id, "quantity": 1, "selected_options": {}})
        order = order_service.checkout(customer_id, "get-order-key")

        found = order_service.get_order(customer_id, order.id)
        assert found.id == order.id


def test_get_order_rejects_other_users_order(app):
    with app.app_context():
        catalog_repo = CatalogRepository()
        order_service = OrderService(OrderRepository(), catalog_repo)
        dish = catalog_repo.get_dish_by_slug("citrus-tofu-bowl")
        customer_id = _user_id("customer")
        moderator_id = _user_id("moderator")

        order_service.add_cart_item(customer_id, {"dish_id": dish.id, "quantity": 1, "selected_options": {}})
        order = order_service.checkout(customer_id, "isolation-key")

        with pytest.raises(AppError) as exc:
            order_service.get_order(moderator_id, order.id)
        assert exc.value.code == "not_found"


def test_list_orders_returns_user_orders(app):
    with app.app_context():
        catalog_repo = CatalogRepository()
        order_service = OrderService(OrderRepository(), catalog_repo)
        dish = catalog_repo.get_dish_by_slug("citrus-tofu-bowl")
        customer_id = _user_id("customer")

        order_service.add_cart_item(customer_id, {"dish_id": dish.id, "quantity": 1, "selected_options": {}})
        order_service.checkout(customer_id, "list-orders-key")

        orders = order_service.list_orders(customer_id)
        assert len(orders) >= 1
        assert all(o.user_id == customer_id for o in orders)


def test_list_orders_empty_for_user_with_no_orders(app):
    with app.app_context():
        order_service = OrderService(OrderRepository(), CatalogRepository())
        moderator_id = _user_id("moderator")

        orders = order_service.list_orders(moderator_id)
        assert orders == []


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
            except Exception as exc:
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
