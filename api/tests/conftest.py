import io
import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://lignee:lignee@localhost:5432/lignee_test"
)
os.environ.setdefault("MEDIA_DIR", "/tmp/lignee-test-media")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.main import app  # noqa: E402

TABLES = [
    "contribution_payment",
    "contribution_due",
    "contribution_event",
    "contribution_scale",
    "delegation",
    "proposal",
    "audit_log",
    "title_holding",
    "title_definition",
    "family_union",
    "parent_child",
    "family_merge",
    "invitation",
    "membership",
    "person",
    "family",
    "app_user",
]


@pytest.fixture(autouse=True)
def clean_db():
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class Api:
    """Petit client de test : un utilisateur connecté, une famille courante."""

    def __init__(self, client: TestClient, email: str, name: str = "Test User"):
        self.c = client
        r = client.post(
            "/api/v1/auth/register",
            json={"full_name": name, "email": email, "password": "motdepasse123"},
        )
        assert r.status_code == 201, r.text
        self.token = r.json()["access_token"]
        self.family_id: str | None = None
        self.person_id: str | None = None

    @property
    def h(self) -> dict:
        h = {"Authorization": f"Bearer {self.token}"}
        if self.family_id:
            h["X-Family-Id"] = self.family_id
        return h

    def get(self, path, **kw):
        return self.c.get(f"/api/v1{path}", headers=self.h, **kw)

    def post(self, path, json=None, **kw):
        return self.c.post(f"/api/v1{path}", json=json, headers=self.h, **kw)

    def patch(self, path, json=None):
        return self.c.patch(f"/api/v1{path}", json=json, headers=self.h)

    def delete(self, path):
        return self.c.delete(f"/api/v1{path}", headers=self.h)

    def create_family(self, name="Famille Test", first="Moi", sex="M"):
        r = self.post("/families", {"name": name, "my_first_name": first, "my_sex": sex})
        assert r.status_code == 201, r.text
        self.family_id = r.json()["id"]
        self.person_id = r.json()["person_id"]
        return r.json()

    def person(self, first, sex="U", parents=(), spouse=None, **extra):
        body = {"first_name": first, "sex": sex, "parent_ids": list(parents), **extra}
        if spouse:
            body["spouse_id"] = spouse
        r = self.post("/persons", body)
        assert r.status_code == 201, r.text
        return r.json()["id"]


@pytest.fixture
def api(client) -> Api:
    a = Api(client, "admin@example.com", "Admin Famille")
    a.create_family()
    return a


def png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1200, 900), (200, 120, 40)).save(buf, format="PNG")
    return buf.getvalue()


def build_family(api: Api) -> dict:
    """Racine → 2 enfants → petits-enfants, avec un conjoint et une seconde épouse."""
    ids = {}
    ids["root"] = api.person("Ngougouré", "F", birth_year=1850, is_living=False)
    ids["husband"] = api.person("Époux", "M", spouse=ids["root"], is_living=False)
    ids["a"] = api.person("Alpha", "M", parents=[ids["root"], ids["husband"]])
    ids["b"] = api.person("Beta", "F", parents=[ids["root"], ids["husband"]])
    ids["a_wife1"] = api.person("Awa", "F", spouse=ids["a"], union_rank=1)
    ids["a_wife2"] = api.person("Bintou", "F", spouse=ids["a"], union_rank=2)
    ids["a1"] = api.person("Ali", "M", parents=[ids["a"], ids["a_wife1"]])
    ids["a2"] = api.person("Amina", "F", parents=[ids["a"], ids["a_wife2"]])
    ids["b1"] = api.person("Bachir", "M", parents=[ids["b"]])
    ids["a1c"] = api.person("Adam", "M", parents=[ids["a1"]])
    ids["b1c"] = api.person("Basma", "F", parents=[ids["b1"]])
    r = api.patch("/families/current", {"root_person_id": ids["root"]})
    assert r.status_code == 200
    return ids


def join_as(client, api: Api, email: str, name: str, person_id=None, role="member") -> Api:
    """Invite un nouveau compte (relié à `person_id`) et le fait entrer dans la famille de `api`."""
    body = {"role": role, **({"person_id": person_id} if person_id else {})}
    inv = api.post("/invitations", body).json()
    guest = Api(client, email, name)
    r = guest.post(f"/invitations/token/{inv['token']}/accept")
    assert r.status_code == 200, r.text
    guest.family_id = r.json()["id"]
    guest.person_id = r.json()["person_id"]
    return guest
