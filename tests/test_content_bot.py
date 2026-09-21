from content_bot import build_captions, slugify


def test_build_captions_includes_all_three_platforms_with_product_details():
    product = {"displayName": "무선청소기", "displayPrice": 24680, "discountRate": 91}
    captions = build_captions(product)
    assert set(captions) == {"threads", "tiktok", "youtube"}
    for text in captions.values():
        assert "무선청소기" in text
        assert "91" in text
        assert "24,680" in text


def test_slugify_replaces_non_alphanumeric_and_collapses_dashes():
    assert slugify("2in1 에어슬림 무선청소기 YQ-669, 화이트, 1개") == "2in1-에어슬림-무선청소기-YQ-669-화이트-1개"


def test_slugify_truncates_to_max_length():
    long_name = "가" * 50
    result = slugify(long_name, max_len=10)
    assert len(result) <= 10


def test_slugify_falls_back_when_name_has_no_keepable_characters():
    assert slugify("···") == "item"
