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
        urllib.request.urlretrieve(url, dest)
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

    products = run_scrape(PROFILE_DIR, output_dir)
    products = generate_all_captions(products)

    for i, product in enumerate(products, start=1):
        folder = output_dir / f"{i:03d}-{slugify(product['name'])}"
        folder.mkdir(parents=True, exist_ok=True)
        download_image(product["imageUrl"], folder / "image.jpg")
        (folder / "link.txt").write_text(product["shareLink"] + "\n", encoding="utf-8")
        write_captions_md(folder / "captions.md", product.get("captions"))

    print(f"완료: {output_dir} ({len(products)}개 상품)")


if __name__ == "__main__":
    main()
