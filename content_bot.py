import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

from sharelink_api import get_access_token, get_today_deals, issue_link

OUTPUT_DIR = Path("output")


def build_captions(product: dict) -> dict:
    name = product["displayName"]
    price = product["displayPrice"]
    discount = product["discountRate"]
    return {
        "threads": f"{name} {discount}% 할인 중! {price:,}원에 득템했어요.",
        "tiktok": f"🔥{discount}% 특가🔥\n{name}\n{price:,}원\n#특가 #꿀템 #가성비",
        "youtube": f"{name}을(를) {discount}% 할인된 {price:,}원에 만나보세요. 재고 소진 시 조기 종료될 수 있어요.",
    }


def slugify(name: str, max_len: int = 30) -> str:
    """폴더명으로 못 쓰는 문자를 하이픈으로 바꾸고 길이를 제한한다."""
    kept = "".join(c if c.isalnum() else "-" for c in name)
    while "--" in kept:
        kept = kept.replace("--", "-")
    slug = kept.strip("-")[:max_len].strip("-")
    return slug or "item"


def download_image(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as e:
        print(f"이미지 다운로드 실패, 건너뜀: {e}", file=sys.stderr)
        return False


def main():
    token = get_access_token()
    products = get_today_deals(token)
    if not products:
        raise SystemExit("하루특가 상품을 하나도 찾지 못했어요.")

    publisher_id = os.environ["SHARELINK_PUBLISHER_ID"]
    today_dir = OUTPUT_DIR / date.today().isoformat()
    today_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for i, product in enumerate(products, start=1):
        name = product["displayName"]
        try:
            share_link = issue_link(token, product["tacaItemId"], publisher_id)
        except Exception as e:
            print(f"링크 발급 실패, 건너뜀: {name} ({e})", file=sys.stderr)
            continue

        folder = today_dir / f"{i:03d}-{slugify(name)}"
        folder.mkdir(parents=True, exist_ok=True)

        download_image(product["thumbnailUrl"], folder / "image.jpg")
        (folder / "link.txt").write_text(share_link + "\n", encoding="utf-8")

        captions = build_captions(product)
        caption_text = "".join(f"## {platform}\n\n{text}\n\n" for platform, text in captions.items())
        (folder / "captions.md").write_text(caption_text, encoding="utf-8")

        manifest.append(
            {
                "name": name,
                "price": product["displayPrice"],
                "discountRate": product["discountRate"],
                "imageUrl": product["thumbnailUrl"],
                "shareLink": share_link,
            }
        )

    (today_dir / "products.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"완료: {today_dir} ({len(manifest)}개 상품)")


if __name__ == "__main__":
    main()
