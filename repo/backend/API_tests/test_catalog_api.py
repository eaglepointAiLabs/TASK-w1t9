from io import BytesIO


def fetch_csrf(client):
    response = client.get("/login")
    html = response.get_data(as_text=True)
    marker = 'name="csrf_token" value="'
    return html.split(marker)[1].split('"')[0]


def login(client, username, password):
    csrf_token = fetch_csrf(client)
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    return response, response.headers.get("X-CSRF-Token", csrf_token)


def test_get_dishes_filters_by_category(client):
    response = client.get("/api/dishes?category=noodles", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.json["data"][0]["category_slug"] == "noodles"


def test_get_dishes_supports_explicit_pagination(client):
    response = client.get("/api/dishes?page=1&page_size=1", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert len(response.json["data"]) <= 1
    assert response.json["pagination"]["page"] == 1
    assert response.json["pagination"]["page_size"] == 1


def test_manager_create_dish_forbidden_for_customer(client):
    _response, csrf_token = login(client, "customer", "Customer#1234")
    response = client.post(
        "/api/manager/dishes",
        json={
            "name": "Forbidden Dish",
            "base_price": "8.00",
            "category_name": "Bowls",
            "availability_windows": [],
            "options": [
                {
                    "name": "Size",
                    "values": [{"label": "Regular", "price_delta": "0.00"}],
                    "rules": [{"rule_type": "single_select_required", "is_required": True, "min_select": 1, "max_select": 1}],
                }
            ],
        },
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 403


def test_manager_can_create_and_publish_dish(client):
    _response, csrf_token = login(client, "manager", "Manager#12345")
    create_response = client.post(
        "/api/manager/dishes",
        json={
            "name": "Manager Special",
            "base_price": "14.00",
            "category_name": "Chef Specials",
            "tags": ["new"],
            "sort_order": 5,
            "availability_windows": [],
            "options": [
                {
                    "name": "Soup Base",
                    "values": [
                        {"label": "Classic", "price_delta": "0.00"},
                        {"label": "Tomato", "price_delta": "1.00"},
                    ],
                    "rules": [{"rule_type": "single_select_required", "is_required": True, "min_select": 1, "max_select": 1}],
                }
            ],
        },
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )

    assert create_response.status_code == 201
    dish_id = create_response.json["data"]["id"]

    publish_response = client.post(
        f"/api/manager/dishes/{dish_id}/publish",
        json={"publish": True},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert publish_response.status_code == 200
    assert publish_response.json["data"]["is_published"] is True


def test_required_option_selection_check_returns_validation_error(client, app):
    from app.repositories.catalog_repository import CatalogRepository

    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("signature-beef-noodles")

    _response, csrf_token = login(client, "customer", "Customer#1234")
    response = client.post(
        f"/api/dishes/{dish.id}/selection-check",
        data={"option_spice_level": "mild"},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )

    assert response.status_code == 400
    assert response.json["code"] == "required_options_missing"


def test_selection_check_hides_unpublished_dish_from_public(client, app):
    """
    An unpublished dish must look indistinguishable from a nonexistent one
    to a non-manager caller. Selection-check must not leak pricing or
    option config for dishes the public list already hides.
    """
    from app.extensions import db
    from app.repositories.catalog_repository import CatalogRepository

    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("signature-beef-noodles")
        dish_id = dish.id
        dish.is_published = False
        db.session.add(dish)
        db.session.commit()

    _response, csrf_token = login(client, "customer", "Customer#1234")
    response = client.post(
        f"/api/dishes/{dish_id}/selection-check",
        data={"option_spice_level": "mild", "option_noodle_type": "thin"},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 404
    assert response.json["code"] == "not_found"


def test_selection_check_hides_archived_dish_from_public(client, app):
    """
    An archived dish (archived_at set) must also 404 for public callers.
    """
    from app.extensions import db
    from app.repositories.catalog_repository import CatalogRepository
    from app.services.time_utils import utc_now_naive

    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("signature-beef-noodles")
        dish_id = dish.id
        dish.archived_at = utc_now_naive()
        db.session.add(dish)
        db.session.commit()

    _response, csrf_token = login(client, "customer", "Customer#1234")
    response = client.post(
        f"/api/dishes/{dish_id}/selection-check",
        data={"option_spice_level": "mild", "option_noodle_type": "thin"},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 404
    assert response.json["code"] == "not_found"


def test_selection_check_allows_store_manager_to_preview_unpublished_dish(client, app):
    """
    Store Managers must still be able to run selection-check against
    unpublished dishes so they can preview the workspace before publishing.
    """
    from app.extensions import db
    from app.repositories.catalog_repository import CatalogRepository

    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("signature-beef-noodles")
        dish_id = dish.id
        dish.is_published = False
        db.session.add(dish)
        db.session.commit()

    _response, csrf_token = login(client, "manager", "Manager#12345")
    response = client.post(
        f"/api/dishes/{dish_id}/selection-check",
        data={"option_spice_level": "mild", "option_noodle_type": "thin"},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    # Manager flow reaches the real validator — if the seeded dish's
    # required options are satisfied, a 200 is expected; otherwise
    # a 400 "required_options_missing" proves the visibility gate did
    # not shadow the dish as missing.
    assert response.status_code in (200, 400)
    assert response.json["code"] != "not_found"


def test_image_validation_rejects_non_png_jpeg(client, app):
    from app.repositories.catalog_repository import CatalogRepository

    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("signature-beef-noodles")

    _response, csrf_token = login(client, "manager", "Manager#12345")
    response = client.post(
        f"/api/manager/dishes/{dish.id}/images",
        data={"image": (BytesIO(b"not-an-image"), "dish.gif")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )

    assert response.status_code == 400
    assert response.json["code"] == "invalid_image_type"


def test_image_validation_rejects_large_file(client, app):
    from app.repositories.catalog_repository import CatalogRepository

    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("signature-beef-noodles")

    _response, csrf_token = login(client, "manager", "Manager#12345")
    large_bytes = b"\x89PNG\r\n\x1a\n" + (b"0" * (2 * 1024 * 1024 + 1))
    response = client.post(
        f"/api/manager/dishes/{dish.id}/images",
        data={"image": (BytesIO(large_bytes), "dish.png")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )

    assert response.status_code == 400
    assert response.json["code"] == "invalid_image_size"


def test_image_validation_rejects_spoofed_content_type(client, app):
    """
    A file claiming Content-Type: image/jpeg but whose bytes are not a real
    JPEG (e.g. a plain-text or GIF payload renamed to .jpg) must fail magic-
    byte validation even though MIME alone would pass.
    """
    from app.repositories.catalog_repository import CatalogRepository

    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("signature-beef-noodles")

    _response, csrf_token = login(client, "manager", "Manager#12345")

    # werkzeug infers image/jpeg from .jpg; the content is GIF89a bytes.
    spoofed_bytes = b"GIF89a\x01\x00\x01\x00\x00\x00\x00;"
    response = client.post(
        f"/api/manager/dishes/{dish.id}/images",
        data={"image": (BytesIO(spoofed_bytes), "dish.jpg")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )

    assert response.status_code == 400
    assert response.json["code"] == "invalid_image_content"


def test_manager_bulk_update_queues_and_applies_changes(app):
    manager_client = app.test_client()
    finance_client = app.test_client()

    _response, manager_csrf = login(manager_client, "manager", "Manager#12345")
    _response, finance_csrf = login(finance_client, "finance", "Finance#12345")

    from app.repositories.catalog_repository import CatalogRepository

    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("signature-beef-noodles")

    queue_response = manager_client.post(
        "/api/manager/dishes/bulk-update",
        json={"dish_ids": [dish.id], "publish": False, "archived": True},
        headers={"X-CSRF-Token": manager_csrf, "Accept": "application/json"},
    )
    assert queue_response.status_code == 202

    process_response = finance_client.post(
        "/api/admin/ops/jobs/process",
        json={"count": 1},
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert process_response.status_code == 200
    assert process_response.json["data"][0]["job_type"] == "bulk_menu_update"
    assert process_response.json["data"][0]["status"] == "completed"

    with app.app_context():
        refreshed = CatalogRepository().get_dish(dish.id)
        assert refreshed.is_published is False
        assert refreshed.archived_at is not None
