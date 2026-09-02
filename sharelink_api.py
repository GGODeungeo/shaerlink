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
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["access_token"]


class ShareLinkAPIError(Exception):
    def __init__(self, error_code: str, reason: str):
        self.error_code = error_code
        super().__init__(reason)


def _get(token: str, path: str) -> dict:
    req = urllib.request.Request(
        f"{API_BASE}{path}", headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if body.get("resultType") == "FAIL":
        error = body.get("error", {})
        raise ShareLinkAPIError(error.get("errorCode", ""), error.get("reason", ""))
    return body


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


def get_category_ids(token: str, max_depth: int) -> list:
    """categoryIds ordered breadth-first: every depth-1 id, then every depth-2
    id, and so on through max_depth. Category counts grow fast with depth
    (16 / 182 / 1,359 / ...), and a quota cutoff can hit mid-run - breadth
    order means a cutoff only ever drops the deepest, priciest level instead
    of an arbitrary partial slice of shallow levels too."""
    roots = _get(token, "/categories")["success"]["categories"]
    ids = []
    level = roots
    for _ in range(max_depth):
        ids.extend(node["categoryId"] for node in level)
        level = [child for node in level for child in node.get("children", [])]
    return ids


def _paginate(token: str, path: str, size: int) -> list:
    items = []
    cursor = None
    while True:
        page_path = f"{path}?size={size}"
        if cursor:
            page_path += f"&cursor={urllib.parse.quote(cursor)}"
        data = _get(token, page_path)["success"]
        items.extend(data["items"])
        if not data["hasNext"]:
            break
        cursor = data["nextCursor"]
    return items


def get_today_deals(token: str) -> list:
    return _paginate(token, "/products/today-deals", size=30)


def get_best_category_products(token: str, category_id: int) -> list:
    return _paginate(token, f"/products/best-categories/{category_id}", size=100)


def get_best_selling_products(token: str) -> list:
    return _paginate(token, "/products/best-selling", size=100)


def issue_link(token: str, taca_item_id: int, publisher_id: str) -> str:
    body = json.dumps({"tacaItemId": taca_item_id, "publisherId": publisher_id}).encode()
    req = urllib.request.Request(
        f"{API_BASE}/links",
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["success"]["shortUrl"]
