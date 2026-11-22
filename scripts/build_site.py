"""Inline data/data.json into web/index.html -> site/index.html (one self-contained page)."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
html = (root / "web" / "index.html").read_text(encoding="utf-8")
data = (root / "data" / "data.json").read_text(encoding="utf-8").replace("</", "<\\/")
out = root / "site" / "index.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html.replace("/*__DATA__*/null", data), encoding="utf-8")
print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
