from generate import build_prompt, parse_caption_response


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
