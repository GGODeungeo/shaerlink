from pathlib import Path
import main


def test_slugify_replaces_spaces_and_truncates():
    assert main.slugify("Cool Product Name") == "Cool-Product-Name"
    assert main.slugify("아토몽드 키즈앤맘") == "아토몽드-키즈앤맘"


def test_write_captions_md_with_captions(tmp_path):
    dest = tmp_path / "captions.md"
    main.write_captions_md(dest, {"threads": "A", "tiktok": "B", "youtube": "C"})
    content = dest.read_text(encoding="utf-8")
    assert "## threads" in content and "A" in content
    assert "## youtube" in content and "C" in content


def test_write_captions_md_without_captions(tmp_path):
    dest = tmp_path / "captions.md"
    main.write_captions_md(dest, None)
    assert "실패" in dest.read_text(encoding="utf-8")


def test_download_image_success(tmp_path, monkeypatch):
    def fake_urlretrieve(url, dest):
        Path(dest).write_bytes(b"fake")

    monkeypatch.setattr(main.urllib.request, "urlretrieve", fake_urlretrieve)
    dest = tmp_path / "image.jpg"
    assert main.download_image("http://example.com/a.jpg", dest) is True
    assert dest.exists()


def test_download_image_failure(tmp_path, monkeypatch):
    def fake_urlretrieve(url, dest):
        raise OSError("boom")

    monkeypatch.setattr(main.urllib.request, "urlretrieve", fake_urlretrieve)
    dest = tmp_path / "image.jpg"
    assert main.download_image("http://example.com/a.jpg", dest) is False
