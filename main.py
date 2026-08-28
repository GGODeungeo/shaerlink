import re
import sys
import urllib.request
from pathlib import Path
from typing import Optional


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
