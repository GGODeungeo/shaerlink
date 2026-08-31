from build_app_data import is_deep_discount, to_app_data


def test_is_deep_discount_threshold():
    assert is_deep_discount({"discountRate": 49}) is False
    assert is_deep_discount({"discountRate": 50}) is True
    assert is_deep_discount({"discountRate": 90}) is True


def test_to_app_data_slims_fields_and_sorts_by_discount_desc():
    products = [
        {
            "name": "낮은할인",
            "price": 1000,
            "discountRate": 55,
            "imageUrl": "https://a",
            "shareLink": "https://toss.im/a",
            "_extraFieldFromScraping": "무시돼야 함",
        },
        {
            "name": "높은할인",
            "price": 2000,
            "discountRate": 80,
            "imageUrl": "https://b",
            "shareLink": "https://toss.im/b",
        },
    ]
    result = to_app_data(products)
    assert result == [
        {
            "name": "높은할인",
            "price": 2000,
            "discountRate": 80,
            "imageUrl": "https://b",
            "shareLink": "https://toss.im/b",
        },
        {
            "name": "낮은할인",
            "price": 1000,
            "discountRate": 55,
            "imageUrl": "https://a",
            "shareLink": "https://toss.im/a",
        },
    ]
