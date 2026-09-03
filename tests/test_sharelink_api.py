import urllib.error

import sharelink_api as api


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
