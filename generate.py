import sys


def generate_captions(product: dict) -> dict:
    name = product["name"]
    price = product["price"]
    discount = product["discountRate"]

    threads = (
        f"오늘 {discount}% 할인 중인 {name}, {price:,}원에 만나보세요. "
        f"30일 내 최저가라 지금이 딱이에요."
    )
    tiktok = f"{discount}% 특가 놓치지 마세요! {name} 단돈 {price:,}원 🔥 #오늘의특가 #가성비"
    youtube = (
        f"{name}을(를) {discount}% 할인된 {price:,}원에 만나보세요. "
        f"30일 내 최저가로 확인된 가격이라 지금이 구매하기 좋은 시점입니다. "
        f"수량이 한정일 수 있으니 서두르세요. 아래 링크에서 바로 확인하실 수 있어요."
    )
    return {"threads": threads, "tiktok": tiktok, "youtube": youtube}


def generate_all_captions(products: list) -> list:
    for product in products:
        try:
            product["captions"] = generate_captions(product)
        except Exception as e:
            print(f"캡션 생성 실패: {product['name']} ({e})", file=sys.stderr)
            product["captions"] = None
    return products
