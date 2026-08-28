import os
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path
from typing import Optional

from scrape import run_scrape
from generate import generate_all_captions

PROFILE_DIR = os.environ.get("BROWSER_PROFILE_DIR", "browser-profile")


def slugify(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)
    return cleaned[:30] or "product"


def download_image(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response, open(dest, "wb") as f:
            f.write(response.read())
        return True
    except Exception as e:
        print(f"이미지 다운로드 실패: {url} ({e})", file=sys.stderr)
        return False


def write_captions_md(dest: Path, captions: Optional[dict]) -> None:
    if captions is None:
        dest.write_text("(캡션 생성 실패)\n", encoding="utf-8")
        return
    lines = []
    for platform in ("threads", "tiktok", "youtube"):
        lines.append(f"## {platform}\n")
        lines.append(captions.get(platform, "").strip() + "\n\n")
    dest.write_text("".join(lines), encoding="utf-8")


def main():
    today = date.today().isoformat()
    output_dir = Path("output") / today

    try:
        products = run_scrape(PROFILE_DIR, output_dir)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    products = generate_all_captions(products)

    image_failures = 0
    for i, product in enumerate(products, start=1):
        folder = output_dir / f"{i:03d}-{slugify(product['name'])}"
        folder.mkdir(parents=True, exist_ok=True)
        if not download_image(product["imageUrl"], folder / "image.jpg"):
            image_failures += 1
        (folder / "link.txt").write_text(product["shareLink"] + "\n", encoding="utf-8")
        write_captions_md(folder / "captions.md", product.get("captions"))

    caption_failures = sum(1 for p in products if p.get("captions") is None)
    print(
        f"완료: {output_dir} ({len(products)}개 상품, "
        f"캡션 실패 {caption_failures}건, 이미지 실패 {image_failures}건)"
    )


if __name__ == "__main__":
    main()
