from generate import generate_captions, generate_all_captions


def test_generate_captions_returns_all_three_platforms():
    product = {"name": "테스트 상품", "price": 12000, "discountRate": 61}
    result = generate_captions(product)
    assert set(result) == {"threads", "tiktok", "youtube"}


def test_generate_captions_includes_product_fields_in_every_caption():
    product = {"name": "테스트 상품", "price": 12000, "discountRate": 61}
    result = generate_captions(product)
    for caption in result.values():
        assert "테스트 상품" in caption
        assert "12,000" in caption
        assert "61" in caption


def test_generate_all_captions_skips_failed_product(monkeypatch, capsys):
    import generate

    calls = {"n": 0}

    def fake_generate_captions(product):
        calls["n"] += 1
        if product["name"] == "실패상품":
            raise RuntimeError("boom")
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
