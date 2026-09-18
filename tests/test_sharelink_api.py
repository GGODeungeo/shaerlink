import io
import json
import urllib.error

import sharelink_api as api


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def headers(self):
        return {}


def test_urlopen_retries_transient_errors_then_succeeds(monkeypatch):
    calls = {"count": 0}

    def fake_urlopen(req, timeout):
        calls["count"] += 1
        if calls["count"] < 3:
            raise urllib.error.URLError("boom")
        return "ok"

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(api.time, "sleep", lambda seconds: None)

    assert api._urlopen(object()) == "ok"
    assert calls["count"] == 3


def test_urlopen_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(
        api.urllib.request,
        "urlopen",
        lambda req, timeout: (_ for _ in ()).throw(urllib.error.URLError("boom")),
    )
    monkeypatch.setattr(api.time, "sleep", lambda seconds: None)

    try:
        api._urlopen(object())
        assert False, "expected URLError to propagate"
    except urllib.error.URLError:
        pass


def test_issue_link_with_origin_raises_on_fail_response_instead_of_returning_none(monkeypatch):
    # Real observed payload: HTTP 200 with resultType FAIL and success:null
    # for an unknown tacaItemId - must not be treated as a successful None.
    body = json.dumps({
        "resultType": "FAIL",
        "success": None,
        "error": {"errorCode": None, "reason": "상품 정보를 찾을 수 없습니다."},
    }).encode()
    monkeypatch.setattr(api, "_urlopen", lambda req: _FakeResponse(body))

    try:
        api.issue_link_with_origin("token", 12345, "publisher-1")
        assert False, "expected ShareLinkAPIError to be raised"
    except api.ShareLinkAPIError as e:
        assert e.args[0] == "상품 정보를 찾을 수 없습니다."
