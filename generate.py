import re

PROMPT_TEMPLATE = """다음 상품에 대해 SNS 홍보 문구를 만들어줘.

상품명: {name}
가격: {price}원
할인율: {discount}%

아래 형식을 반드시 그대로 지켜서 출력해:

## threads
(캐주얼한 말투, 2~3문장, 이모지 최소화)

## tiktok
(짧고 후킹되는 한 문장 + 해시태그 2~3개)

## youtube
(설명형, 상품 특징과 할인 포인트를 3~4문장으로)
"""

SECTION_RE = re.compile(r"^##\s*(threads|tiktok|youtube)\s*$", re.MULTILINE)


def build_prompt(product: dict) -> str:
    return PROMPT_TEMPLATE.format(
        name=product["name"], price=product["price"], discount=product["discountRate"]
    )


def parse_caption_response(text: str) -> dict:
    parts = SECTION_RE.split(text)
    result = {}
    for i in range(1, len(parts), 2):
        platform = parts[i].strip().lower()
        content = parts[i + 1].strip()
        result[platform] = content
    return result
