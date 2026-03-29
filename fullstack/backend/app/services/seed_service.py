from __future__ import annotations

from datetime import datetime, timedelta

from app.extensions import db
from app.models import Role, UserRole
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.community_repository import CommunityRepository
from app.repositories.moderation_repository import ModerationRepository
from app.repositories.auth_repository import AuthRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.services.auth_service import AuthService
from app.services.catalog_service import CatalogService
from app.services.community_service import CommunityService
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService


DEFAULT_USERS = {
    "customer": {"password": "Customer#1234", "role": "Customer"},
    "manager": {"password": "Manager#12345", "role": "Store Manager"},
    "finance": {"password": "Finance#12345", "role": "Finance Admin"},
    "moderator": {"password": "Moderator#123", "role": "Moderator"},
}


def seed_identity_data() -> None:
    repository = AuthRepository()
    service = AuthService(repository)

    existing_roles = {role.name: role for role in db.session.query(Role).all()}
    for role_name in ["Customer", "Store Manager", "Finance Admin", "Moderator"]:
        if role_name not in existing_roles:
            role = Role(name=role_name)
            db.session.add(role)
            existing_roles[role_name] = role

    db.session.flush()

    for username, config in DEFAULT_USERS.items():
        user = repository.get_user_by_username(username)
        if user is None:
            user = service.create_user_with_password(username, config["password"])

        role = existing_roles[config["role"]]
        exists = next((assignment for assignment in user.roles if assignment.role_id == role.id), None)
        if exists is None:
            db.session.add(UserRole(user_id=user.id, role_id=role.id))

    db.session.commit()


def seed_catalog_data() -> None:
    repository = CatalogRepository()
    service = CatalogService(repository)
    if repository.list_dishes(published_only=False):
        return

    sample_dishes = [
        {
            "name": "Signature Beef Noodles",
            "slug": "signature-beef-noodles",
            "description": "Slow-braised beef broth with hand-pulled noodles.",
            "base_price": "12.50",
            "category_name": "Noodles",
            "tags": ["popular", "spicy"],
            "is_published": True,
            "stock_quantity": 1,
            "sort_order": 10,
            "availability_windows": [
                {"day_of_week": 0, "start_time": "11:00", "end_time": "14:30"},
            ],
            "options": [
                {
                    "name": "Spice Level",
                    "code": "spice_level",
                    "display_type": "single_select",
                    "rules": [{"rule_type": "single_select_required", "is_required": True, "min_select": 1, "max_select": 1}],
                    "values": [
                        {"label": "Mild", "value_code": "mild", "price_delta": "0.00"},
                        {"label": "Medium", "value_code": "medium", "price_delta": "0.00"},
                        {"label": "Hot", "value_code": "hot", "price_delta": "0.50"},
                    ],
                },
                {
                    "name": "Portion Size",
                    "code": "portion_size",
                    "display_type": "single_select",
                    "rules": [{"rule_type": "single_select_required", "is_required": True, "min_select": 1, "max_select": 1}],
                    "values": [
                        {"label": "Regular", "value_code": "regular", "price_delta": "0.00"},
                        {"label": "Large", "value_code": "large", "price_delta": "2.00"},
                    ],
                },
            ],
        },
        {
            "name": "Citrus Tofu Bowl",
            "slug": "citrus-tofu-bowl",
            "description": "Bright tofu bowl with greens and sesame dressing.",
            "base_price": "10.25",
            "category_name": "Bowls",
            "tags": ["vegetarian", "fresh"],
            "is_published": True,
            "stock_quantity": 8,
            "sort_order": 20,
            "availability_windows": [],
            "options": [
                {
                    "name": "Add-ons",
                    "code": "addons",
                    "display_type": "multi_select",
                    "rules": [{"rule_type": "bounded_multi_select", "is_required": False, "min_select": 0, "max_select": 2}],
                    "values": [
                        {"label": "Avocado", "value_code": "avocado", "price_delta": "1.25"},
                        {"label": "Egg", "value_code": "egg", "price_delta": "0.95"},
                    ],
                }
            ],
        },
    ]

    for payload in sample_dishes:
        service.create_dish(payload, ["Store Manager"])


def seed_all() -> None:
    seed_identity_data()
    seed_catalog_data()
    seed_ordering_data()
    seed_payment_keys()
    seed_community_data()
    seed_moderation_data()


def seed_ordering_data() -> None:
    if db.session.execute(db.text("select count(*) from orders")).scalar():
        return

    customer = AuthRepository().get_user_by_username("customer")
    dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")
    if customer is None or dish is None:
        return

    service = OrderService(OrderRepository(), CatalogRepository())
    service.add_cart_item(
        customer.id,
        {"dish_id": dish.id, "quantity": 1, "selected_options": {"addons": ["avocado"]}},
    )
    service.checkout(customer.id, "seed-order-checkout")


def seed_payment_keys() -> None:
    service = PaymentService(PaymentRepository())
    base_time = datetime(2026, 1, 1)
    service.create_signing_key(
        key_id="simulator-v1",
        secret="simulator-secret-v1",
        active_from=base_time,
        expires_at=base_time + timedelta(days=180),
        is_active=True,
    )
    service.create_signing_key(
        key_id="simulator-v2",
        secret="simulator-secret-v2",
        active_from=base_time + timedelta(days=181),
        expires_at=None,
        is_active=True,
    )


def seed_community_data() -> None:
    repository = CommunityRepository()
    if repository.list_posts():
        return
    customer = AuthRepository().get_user_by_username("customer")
    dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")
    repository.create_post(
        author_user_id=customer.id,
        title="Best Lunch Combo",
        body="The citrus tofu bowl still holds up after multiple visits.",
        target_dish_id=dish.id if dish else None,
    )
    db.session.commit()


def seed_moderation_data() -> None:
    repository = ModerationRepository()
    defaults = [
        ("abuse_content", "Abusive Content", "Content contains abusive or hateful language.", "content"),
        ("spam_behavior", "Spam Behavior", "Repeated spam or low-quality posting.", "behavior"),
        ("harassment", "Harassment", "Targeted harassment or threats.", "behavior"),
        ("policy_other", "Policy Other", "Other policy issue requiring action.", "content"),
    ]
    for code, label, description, category in defaults:
        repository.get_or_create_reason_code(code, label, description, category)
    db.session.commit()
