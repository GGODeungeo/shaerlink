import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN_URL = "https://oauth2.cert.toss.im/token"
API_BASE = "https://sharelink.toss.im/openapi"


def _load_dotenv(path: str = ".env") -> None:
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def get_access_token() -> str:
    data = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": os.environ["SHARELINK_ACCESS_KEY"],
            "client_secret": os.environ["SHARELINK_SECRET_KEY"],
            "scope": "sharelink:read sharelink:write",
        }
    ).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)["access_token"]


def _get(token: str, path: str) -> dict:
    req = urllib.request.Request(
        f"{API_BASE}{path}", headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def get_top_level_category_map(token: str) -> dict:
    """Returns {categoryId: rootDisplayName} for every category at any depth,
    mapped to the display name of its top-level (level 1) ancestor - so any
    categoryId found on a product can be bucketed into one of the top-level
    sections regardless of how specific that id is."""
    roots = _get(token, "/categories")["success"]["categories"]
    id_to_root_name = {}

    def walk(nodes, root_name):
        for node in nodes:
            id_to_root_name[node["categoryId"]] = root_name
            walk(node.get("children", []), root_name)

    for root in roots:
        walk([root], root["displayName"])

    return id_to_root_name


def get_top_level_category_ids(token: str) -> list:
    roots = _get(token, "/categories")["success"]["categories"]
    return [root["categoryId"] for root in roots]


def get_today_deals(token: str) -> list:
    items = []
    cursor = None
    while True:
        path = "/products/today-deals?size=30"
        if cursor:
            path += f"&cursor={urllib.parse.quote(cursor)}"
        data = _get(token, path)["success"]
        items.extend(data["items"])
        if not data["hasNext"]:
            break
        cursor = data["nextCursor"]
    return items


def get_best_category_products(token: str, category_id: int) -> list:
    items = []
    cursor = None
    while True:
        path = f"/products/best-categories/{category_id}?size=100"
        if cursor:
            path += f"&cursor={urllib.parse.quote(cursor)}"
        data = _get(token, path)["success"]
        items.extend(data["items"])
        if not data["hasNext"]:
            break
        cursor = data["nextCursor"]
    return items


def issue_link(token: str, taca_item_id: int, publisher_id: str) -> str:
    body = json.dumps({"tacaItemId": taca_item_id, "publisherId": publisher_id}).encode()
    req = urllib.request.Request(
        f"{API_BASE}/links",
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)["success"]["shortUrl"]
