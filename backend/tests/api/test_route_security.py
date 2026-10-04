"""Default deny: every API route must be @public or @require_role(...) (spec 02 task 8)."""

import pytest

PUBLIC_ALLOWLIST = {"/api/health", "/api/webhooks/clerk"}


@pytest.mark.parametrize("app_fixture", ["admin_app", "pos_app"])
def test_every_route_is_protected_or_explicitly_public(request, app_fixture):
    app = request.getfixturevalue(app_fixture)
    problems = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        view = app.view_functions[rule.endpoint]
        is_public = getattr(view, "_shopdesk_public", False)
        roles = getattr(view, "_shopdesk_roles", None)
        if is_public and rule.rule not in PUBLIC_ALLOWLIST:
            problems.append(f"{rule.rule} is public but not on the allowlist")
        if not is_public and not roles:
            problems.append(f"{rule.rule} has no @require_role")
    assert problems == []


def test_pos_server_has_no_admin_routes(pos_app):
    rules = {r.rule for r in pos_app.url_map.iter_rules()}
    assert not any(r.startswith(("/api/users", "/api/webhooks", "/api/audit")) for r in rules)
