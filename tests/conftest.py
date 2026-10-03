import pytest
from app.main import app
from app.core.security import AuthenticatedUser, get_current_user, require_service_or_admin


@pytest.fixture(autouse=True)
def _default_test_auth_override():
    admin_user = AuthenticatedUser(user_id=1, role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[require_service_or_admin] = lambda: admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_service_or_admin, None)
