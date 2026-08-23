import re
import pathlib

site = pathlib.Path("upf_insight/business_site")
files = list(site.rglob("*.html"))
bad = []
for p in files:
    base = p.parent
    html = p.read_text(encoding="utf-8")
    for href in re.findall(r'href="([^"]+)"', html):
        if href.startswith(("http", "#", "data:")):
            continue
        target = (base / href.split("#")[0]).resolve()
        if not target.exists():
            bad.append(f"{p.name} -> {href}")
print("\n".join(bad) if bad else f"ALL LINKS OK across {len(files)} pages")
