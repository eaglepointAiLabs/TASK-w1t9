from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from flask import render_template


def _pending_refund_fixture() -> SimpleNamespace:
    return SimpleNamespace(
        id="refund-component-1",
        refund_reference="refund-component-1",
        transaction_reference="tx-component-1",
        status="pending_stepup",
        requested_amount=Decimal("60.00"),
        hold_reason="amount_stepup_threshold",
        stepup_required="true",
        events=[],
    )


def test_login_hides_seeded_credentials_without_local_review_mode(client):
    response = client.get("/login")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Seeded accounts" not in html
    assert "Account hints are hidden." in html


def test_login_shows_seeded_credentials_when_local_review_mode_enabled(app):
    app.config["SHOW_SEEDED_CREDENTIALS"] = True
    client = app.test_client()

    response = client.get("/login")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Seeded accounts" in html
    assert "Customer#1234" in html
    assert "Admin#123456" in html
    assert "Finance#12345" in html


def test_refund_status_component_only_renders_approval_form_for_store_manager(app):
    refund = _pending_refund_fixture()
    with app.test_request_context("/"):
        manager_html = render_template(
            "partials/refund_status.html",
            refund=refund,
            current_roles=["Store Manager"],
        )
        finance_html = render_template(
            "partials/refund_status.html",
            refund=refund,
            current_roles=["Finance Admin"],
        )

    assert "refund-approval-form" in manager_html
    assert 'data-auto-nonce-purpose="refund:approve"' in manager_html
    assert "Approve high-risk refund" in manager_html

    assert "Store Manager approval is required before this refund can be released." in finance_html
    assert "refund-approval-form" not in finance_html


def test_hx_mutation_forms_include_submit_locking_hooks():
    js_path = Path(__file__).resolve().parents[2] / "backend" / "app" / "static" / "js" / "htmx-lite.js"
    css_path = Path(__file__).resolve().parents[2] / "backend" / "app" / "static" / "css" / "app.css"

    js_text = js_path.read_text(encoding="utf-8")
    css_text = css_path.read_text(encoding="utf-8")

    assert 'form.dataset.submitting === "true"' in js_text
    assert "setFormPending(form, true)" in js_text
    assert "setFormPending(form, false)" in js_text
    assert "form.is-submitting" in css_text
    assert "button:disabled" in css_text
