from types import SimpleNamespace
import pytest
import generate
from generate import build_prompt, parse_caption_response, generate_captions, generate_all_captions


class FakeClient:
    def __init__(self, text):
        self._text = text
        self.last_kwargs = None

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._text)])


def test_build_prompt_includes_product_fields():
    product = {"name": "테스트 상품", "price": 12000, "discountRate": 61}
    prompt = build_prompt(product)
    assert "테스트 상품" in prompt
    assert "12000" in prompt
    assert "61" in prompt


def test_parse_caption_response_splits_three_sections():
    text = (
        "## threads\n"
        "쓰레드용 문구\n\n"
        "## tiktok\n"
        "틱톡용 문구 #특가\n\n"
        "## youtube\n"
        "유튜브용 설명\n"
    )
    result = parse_caption_response(text)
    assert result == {
        "threads": "쓰레드용 문구",
        "tiktok": "틱톡용 문구 #특가",
        "youtube": "유튜브용 설명",
    }


def test_generate_captions_uses_client_and_parses_response(monkeypatch):
    fake_text = "## threads\nA\n\n## tiktok\nB\n\n## youtube\nC\n"
    fake_client = FakeClient(fake_text)
    monkeypatch.setattr(generate, "get_client", lambda: fake_client)
    product = {"name": "테스트", "price": 1000, "discountRate": 10}
    result = generate_captions(product)
    assert result == {"threads": "A", "tiktok": "B", "youtube": "C"}
    # Claude Sonnet 5 runs adaptive thinking by default, which puts a
    # ThinkingBlock (no .text) at content[0] - thinking must be explicitly
    # disabled so the text block can be found by type instead of index.
    assert fake_client.last_kwargs["thinking"] == {"type": "disabled"}
    assert fake_client.last_kwargs["max_tokens"] == 2000


def test_generate_captions_finds_text_block_when_not_first(monkeypatch):
    # Simulate a response where a non-text block precedes the text block
    # (e.g. a thinking block), proving we select by type, not by index.
    fake_text = "## threads\nA\n\n## tiktok\nB\n\n## youtube\nC\n"

    class ThinkingThenTextClient:
        @property
        def messages(self):
            return self

        def create(self, **kwargs):
            return SimpleNamespace(content=[
                SimpleNamespace(type="thinking", thinking="hmm"),
                SimpleNamespace(type="text", text=fake_text),
            ])

    monkeypatch.setattr(generate, "get_client", lambda: ThinkingThenTextClient())
    product = {"name": "테스트", "price": 1000, "discountRate": 10}
    result = generate_captions(product)
    assert result == {"threads": "A", "tiktok": "B", "youtube": "C"}


def test_generate_captions_raises_on_missing_section(monkeypatch):
    # Missing the "youtube" section - a partial/malformed model response
    # must raise instead of silently returning a dict missing a key.
    fake_text = "## threads\nA\n\n## tiktok\nB\n"
    monkeypatch.setattr(generate, "get_client", lambda: FakeClient(fake_text))
    product = {"name": "테스트", "price": 1000, "discountRate": 10}
    with pytest.raises(ValueError):
        generate_captions(product)


def test_generate_all_captions_skips_failed_product(monkeypatch, capsys):
    calls = {"n": 0}

    def fake_generate_captions(product):
        calls["n"] += 1
        if product["name"] == "실패상품":
            raise RuntimeError("api down")
        return {"threads": "ok", "tiktok": "ok", "youtube": "ok"}

    monkeypatch.setattr(generate, "generate_captions", fake_generate_captions)
    products = [
        {"name": "실패상품", "price": 1, "discountRate": 1},
        {"name": "정상상품", "price": 2, "discountRate": 2},
    ]
    result = generate_all_captions(products)
    assert result[0]["captions"] is None
    assert result[1]["captions"] == {"threads": "ok", "tiktok": "ok", "youtube": "ok"}
    assert calls["n"] == 2


def test_generate_all_captions_isolates_malformed_response(monkeypatch, capsys):
    good_text = "## threads\nA\n\n## tiktok\nB\n\n## youtube\nC\n"
    bad_text = "## threads\nA\n\n## tiktok\nB\n"  # missing youtube section

    class RoutingClient:
        @property
        def messages(self):
            return self

        def create(self, **kwargs):
            content = kwargs["messages"][0]["content"]
            text = bad_text if "불완전상품" in content else good_text
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])

    monkeypatch.setattr(generate, "get_client", lambda: RoutingClient())
    products = [
        {"name": "불완전상품", "price": 1, "discountRate": 1},
        {"name": "정상상품", "price": 2, "discountRate": 2},
    ]
    result = generate_all_captions(products)
    assert result[0]["captions"] is None
    assert result[1]["captions"] == {"threads": "A", "tiktok": "B", "youtube": "C"}
