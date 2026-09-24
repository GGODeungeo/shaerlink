"""Sharelink '주문 이벤트 수신' webhook receiver.

On a verified PURCHASE event, grants the sharelink click's promotion reward
via the apps-in-toss mTLS server-to-server API, using partnerRefId (the
buyer's getAnonymousKey() hash) as the anon-key target.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import json
import os
import psycopg2
import ssl
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler

MAX_CLOCK_SKEW = timedelta(minutes=5)
PROMOTION_API_HOST = "apps-in-toss-api.toss.im"
PRODUCTS_DB_URL_ENV = "PRODUCTS_DB_DATABASE_URL"

# 클라이언트(App.tsx)의 기존 SORT_OPTIONS와 동일한 3종만 지원.
# (컬럼명, 방향) - 방향은 정렬 컬럼과 커서 타이브레이커 컬럼 모두에 동일하게 적용된다.
SORT_COLUMNS = {
    "recommend": ("review_count", "desc"),
    "discount": ("discount_rate", "desc"),
    "price": ("price", "asc"),
}

# ponytail: in-memory only - resets on cold start / differs per instance, so a
# retried webhook hitting a fresh instance can still double-grant. Move to a
# shared store (Vercel KV/Upstash) if duplicate rewards actually show up.
_processed_order_ids = set()


def _verify_signature(raw_body: bytes, transmission_time: str, signature: str, secret: str) -> bool:
    if not (transmission_time and signature and signature.startswith("v1:")):
        return False
    message = raw_body + b":" + transmission_time.encode()
    expected = "v1:" + base64.b64encode(
        hmac.new(secret.encode(), message, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, signature)


def _within_clock_skew(transmission_time: str) -> bool:
    try:
        sent_at = datetime.fromisoformat(transmission_time)
    except ValueError:
        return False
    now = datetime.now(timezone.utc)
    return abs(now - sent_at.astimezone(timezone.utc)) <= MAX_CLOCK_SKEW


def _write_temp_pem(env_var: str) -> str:
    content = base64.b64decode(os.environ[env_var])
    fd, path = tempfile.mkstemp(suffix=".pem")
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


_mtls_context = None


def _mtls_ssl_context() -> ssl.SSLContext:
    global _mtls_context
    if _mtls_context is None:
        cert_path = _write_temp_pem("MTLS_CERT_B64")
        key_path = _write_temp_pem("MTLS_PRIVATE_KEY_B64")
        context = ssl.create_default_context()
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        _mtls_context = context
    return _mtls_context


def _promotion_api_post(path: str, anon_key: str, body: dict) -> dict:
    conn = http.client.HTTPSConnection(PROMOTION_API_HOST, context=_mtls_ssl_context(), timeout=10)
    try:
        conn.request(
            "POST",
            path,
            body=json.dumps(body),
            headers={"Content-Type": "application/json", "x-anon-key": anon_key},
        )
        resp = conn.getresponse()
        return json.loads(resp.read())
    finally:
        conn.close()


def is_reward_eligible(event: dict, min_purchase_amount: int, processed_order_ids: set) -> bool:
    return (
        event.get("eventType") == "PURCHASE"
        and bool(event.get("partnerRefId"))
        and event.get("orderId") not in processed_order_ids
        and (event.get("commissionBaseAmount") or 0) >= min_purchase_amount
    )


def grant_reward(anon_key: str, amount: int, promotion_code: str | None = None) -> dict:
    promotion_code = promotion_code or os.environ["PROMOTION_CODE"]

    key_resp = _promotion_api_post(
        "/api-partner/v1/apps-in-toss/promotion/execute-promotion/get-key", anon_key, {}
    )
    if key_resp.get("resultType") != "SUCCESS":
        return key_resp
    reward_key = key_resp["success"]["key"]

    return _promotion_api_post(
        "/api-partner/v1/apps-in-toss/promotion/execute-promotion",
        anon_key,
        {"promotionCode": promotion_code, "key": reward_key, "amount": amount},
    )


def grant_click_reward(anon_key: str) -> None:
    """Best-effort reward grant for clicking through to the sharelink itself,
    separate from the PURCHASE-triggered reward above (different promotion,
    tiny amount). Never raises - a failed/capped grant (daily limit hit,
    promotion paused) must not break link issuance."""
    click_promotion_code = os.environ.get("CLICK_PROMOTION_CODE")
    if not click_promotion_code:
        return
    amount = int(os.environ.get("CLICK_REWARD_AMOUNT_WON", "1"))
    try:
        result = grant_reward(anon_key, amount, promotion_code=click_promotion_code)
        print(f"[click-reward] anonKey={anon_key} result={result}")
    except Exception as e:
        print(f"[click-reward] failed for anonKey={anon_key}: {e}")


def issue_tracked_link(taca_item_id: int, anon_key: str) -> str:
    """Issues a fresh sharelink for this click and tags its originUrl with
    partner_ref_id=anon_key, so a later PURCHASE webhook can attribute the
    order back to this app user.

    Sharelink's Open API enforces a source-IP allowlist that Vercel's
    dynamic egress IP can't satisfy, so the actual issuance happens on a
    small static-IP relay droplet instead - this just forwards to it."""
    req = urllib.request.Request(
        os.environ["RELAY_URL"],
        data=json.dumps({"tacaItemId": taca_item_id}).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "x-relay-token": os.environ["RELAY_TOKEN"]},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        link = json.loads(resp.read())

    origin = link["originUrl"]
    sep = "&" if "?" in origin else "?"
    return f"{origin}{sep}partner_ref_id={urllib.parse.quote(anon_key, safe='')}"


def encode_cursor(row: dict) -> str:
    payload = json.dumps([row["sort_value"], row["source"], row["source_item_id"]])
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple:
    payload = base64.urlsafe_b64decode(cursor.encode()).decode()
    sort_value, source, source_item_id = json.loads(payload)
    return sort_value, source, source_item_id


def build_products_query(
    category: str | None, search: str | None, sort: str, cursor: str | None, limit: int
) -> tuple:
    """category XOR search 중 하나로 필터링해서 (SQL, params)를 만든다.
    OFFSET 없이 keyset 방식 - 정렬 컬럼과 타이브레이커(source,
    source_item_id)를 같은 방향으로 묶어서 튜플 비교한다."""
    if sort not in SORT_COLUMNS:
        raise ValueError(f"unknown sort: {sort}")
    column, direction = SORT_COLUMNS[sort]
    comparator = "<" if direction == "desc" else ">"

    where_clauses = []
    params: list = []
    if category is not None:
        where_clauses.append("category = %s")
        params.append(category)
    if search is not None:
        where_clauses.append("name ilike %s")
        params.append(f"%{search}%")

    if cursor is not None:
        sort_value, cur_source, cur_source_item_id = decode_cursor(cursor)
        where_clauses.append(
            f"({column}, source, source_item_id) {comparator} (%s, %s, %s)"
        )
        params.extend([sort_value, cur_source, cur_source_item_id])

    where_sql = " and ".join(where_clauses)
    sql = (
        f"select * from products where {where_sql} "
        f"order by {column} {direction}, source {direction}, source_item_id {direction} "
        f"limit %s"
    )
    params.append(limit)
    return sql, params


def _row_to_product(row: tuple, columns: list) -> dict:
    record = dict(zip(columns, row))
    product = {
        "tacaItemId": record["source_item_id"],
        "shareLink": record["share_link"],
        "name": record["name"],
        "price": record["price"],
        "discountRate": record["discount_rate"],
        "imageUrl": record["image_url"],
        "category": record["category"],
        "reviewCount": record["review_count"],
        "isAllTimeLow": record["is_all_time_low"],
    }
    if record["deal_ends_at"] is not None:
        product["dealEndsAt"] = record["deal_ends_at"].isoformat()
    return product


def fetch_products_page(
    conn, category: str | None, search: str | None, sort: str, cursor: str | None, limit: int
) -> dict:
    sql, params = build_products_query(category, search, sort, cursor, limit)
    column, _direction = SORT_COLUMNS[sort]
    with conn.cursor() as cur:
        cur.execute(sql, params)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    items = [_row_to_product(row, columns) for row in rows]

    next_cursor = None
    if len(rows) == limit:
        last = dict(zip(columns, rows[-1]))
        next_cursor = encode_cursor({
            "sort_value": last[column],
            "source": last["source"],
            "source_item_id": last["source_item_id"],
        })

    return {"items": items, "nextCursor": next_cursor}


def fetch_home_products(conn) -> list:
    """카테고리별 상위 20 + 역대최저가 상위 20 + 캐러셀 후보(할인 80%+) 상위
    20 + 전역 리뷰순 상위 30(카테고리 무관 - PopularRanking/TodaysPickEvent가
    이 배열에서 직접 정렬·slice하므로 여기 없으면 두 화면에서 빠질 수 있음)을
    합쳐 review_count 순으로 반환한다."""
    sql = """
        with category_top as (
            select *, row_number() over (partition by category order by review_count desc) as rn
            from products
        ),
        all_time_low_top as (
            select *, row_number() over (order by review_count desc) as rn
            from products where is_all_time_low
        ),
        carousel_top as (
            select *, row_number() over (order by review_count desc) as rn
            from products where discount_rate >= 80
        ),
        global_top as (
            select *, row_number() over (order by review_count desc) as rn
            from products
        )
        select distinct on (share_link) *
        from (
            select * from category_top where rn <= 20
            union all
            select * from all_time_low_top where rn <= 20
            union all
            select * from carousel_top where rn <= 20
            union all
            select * from global_top where rn <= 30
        ) combined
        order by share_link, review_count desc
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    return [_row_to_product(row, columns) for row in rows]


def fetch_products_by_ids(conn, share_links: list) -> list:
    """찜/최근본처럼 임의의 shareLink 목록으로 정확히 그 상품들만 조회한다.
    순서는 보장하지 않음 - 호출 측(App.tsx)이 로컬에 저장된 순서대로
    재배열한다. 존재하지 않는 shareLink는 결과에서 조용히 빠진다."""
    if not share_links:
        return []
    with conn.cursor() as cur:
        cur.execute("select * from products where share_link = any(%s)", (share_links,))
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    return [_row_to_product(row, columns) for row in rows]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/products/home":
            self._handle_home_products_request()
        elif path == "/api/products/batch":
            self._handle_products_batch_request()
        elif path == "/api/products":
            self._handle_products_page_request()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path.startswith("/api/link"):
            self._handle_link_request()
        elif self.path.startswith("/api/test-reward"):
            self._handle_test_reward_request()
        else:
            self._handle_order_event()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, x-internal-token")
        self.end_headers()

    def _handle_home_products_request(self):
        db_url = os.environ.get(PRODUCTS_DB_URL_ENV)
        if not db_url:
            self._respond(500, {"error": "PRODUCTS_DB_DATABASE_URL not configured"}, cors=True)
            return
        conn = psycopg2.connect(db_url)
        try:
            items = fetch_home_products(conn)
        finally:
            conn.close()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(items).encode())

    def _handle_products_batch_request(self):
        db_url = os.environ.get(PRODUCTS_DB_URL_ENV)
        if not db_url:
            self._respond(500, {"error": "PRODUCTS_DB_DATABASE_URL not configured"}, cors=True)
            return

        query = urllib.parse.urlparse(self.path).query
        parsed = urllib.parse.parse_qs(query)
        ids_param = parsed.get("ids", [""])[0]
        share_links = [s for s in ids_param.split(",") if s]
        if not share_links:
            self._respond(400, {"error": "ids is required"}, cors=True)
            return

        conn = psycopg2.connect(db_url)
        try:
            items = fetch_products_by_ids(conn, share_links)
        finally:
            conn.close()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"items": items}).encode())

    def _handle_products_page_request(self):
        db_url = os.environ.get(PRODUCTS_DB_URL_ENV)
        if not db_url:
            self._respond(500, {"error": "PRODUCTS_DB_DATABASE_URL not configured"}, cors=True)
            return

        query = urllib.parse.urlparse(self.path).query
        parsed = urllib.parse.parse_qs(query)
        category = parsed.get("category", [None])[0]
        search = parsed.get("search", [None])[0]
        sort = parsed.get("sort", ["recommend"])[0]
        cursor = parsed.get("cursor", [None])[0]
        limit = int(parsed.get("limit", ["20"])[0])

        if not category and not search:
            self._respond(400, {"error": "category or search is required"}, cors=True)
            return
        if category and search:
            self._respond(400, {"error": "category and search are mutually exclusive"}, cors=True)
            return

        conn = psycopg2.connect(db_url)
        try:
            result = fetch_products_page(conn, category, search, sort, cursor, limit)
        except ValueError as e:
            self._respond(400, {"error": str(e)}, cors=True)
            return
        finally:
            conn.close()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"items": result["items"], "nextCursor": result["nextCursor"]}).encode())

    def _handle_order_event(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)
        transmission_time = self.headers.get("sharelink-webhook-transmission-time", "")
        signature = self.headers.get("sharelink-webhook-signature", "")
        secret = os.environ.get("SHARELINK_SECRET_KEY", "")

        if not secret or not _verify_signature(raw_body, transmission_time, signature, secret):
            self._respond(401, {"error": "invalid signature"})
            return
        if not _within_clock_skew(transmission_time):
            self._respond(401, {"error": "stale timestamp"})
            return

        event = json.loads(raw_body)
        order_id = event.get("orderId")
        min_purchase = int(os.environ.get("MIN_PURCHASE_AMOUNT_WON", "5000"))
        print(f"[order-event] {event.get('eventType')} partnerRefId={event.get('partnerRefId')} "
              f"orderId={order_id} amount={event.get('commissionBaseAmount')}")

        if is_reward_eligible(event, min_purchase, _processed_order_ids):
            amount = int(os.environ.get("REWARD_AMOUNT_WON", "500"))
            result = grant_reward(event["partnerRefId"], amount)
            print(f"[reward] orderId={order_id} result={result}")
            if result.get("resultType") == "SUCCESS":
                _processed_order_ids.add(order_id)

        self._respond(200, {"received": True})

    def _handle_link_request(self):
        token = self.headers.get("x-internal-token", "")
        if not hmac.compare_digest(token.encode(), os.environ.get("LINK_API_TOKEN", "").encode()):
            self._respond(401, {"error": "unauthorized"}, cors=True)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(content_length) or b"{}")
            taca_item_id = int(body["tacaItemId"])
            anon_key = str(body["anonKey"])
        except (json.JSONDecodeError, KeyError, ValueError):
            self._respond(400, {"error": "tacaItemId and anonKey are required"}, cors=True)
            return

        print(f"[link] request tacaItemId={taca_item_id} anonKey={anon_key}")
        try:
            url = issue_tracked_link(taca_item_id, anon_key)
        except Exception as e:
            print(f"[link] issue failed for tacaItemId={taca_item_id}: {e}")
            self._respond(502, {"error": "link issuance failed"}, cors=True)
            return

        grant_click_reward(anon_key)
        self._respond(200, {"url": url}, cors=True)

    def _handle_test_reward_request(self):
        """Manual test hook for the promotion pre-launch gate: lets us call
        execute-promotion with a TEST_-prefixed code (see promotion docs)
        without touching the live PROMOTION_CODE/CLICK_PROMOTION_CODE env
        vars. Same auth token as /api/link since both are internal-only."""
        token = self.headers.get("x-internal-token", "")
        if not hmac.compare_digest(token.encode(), os.environ.get("LINK_API_TOKEN", "").encode()):
            self._respond(401, {"error": "unauthorized"}, cors=True)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(content_length) or b"{}")
            promotion_code = str(body["promotionCode"])
            anon_key = str(body["anonKey"])
            amount = int(body["amount"])
        except (json.JSONDecodeError, KeyError, ValueError):
            self._respond(400, {"error": "promotionCode, anonKey and amount are required"}, cors=True)
            return

        result = grant_reward(anon_key, amount, promotion_code=promotion_code)
        print(f"[test-reward] promotionCode={promotion_code} anonKey={anon_key} result={result}")
        self._respond(200, result, cors=True)

    def _respond(self, status: int, body: dict, cors: bool = False):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)
