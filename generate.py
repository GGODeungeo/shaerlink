import os
import re
import sys
import anthropic

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

MODEL = "claude-sonnet-5"
_client = None


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


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def generate_captions(product: dict) -> dict:
    prompt = build_prompt(product)
    response = get_client().messages.create(
        model=MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_caption_response(response.content[0].text)


def generate_all_captions(products: list[dict]) -> list[dict]:
    for product in products:
        try:
            product["captions"] = generate_captions(product)
        except Exception as e:
            print(f"캡션 생성 실패: {product['name']} ({e})", file=sys.stderr)
            product["captions"] = None
    return products
