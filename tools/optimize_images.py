"""Make light WebP copies of heavy images for fast mobile loading.

Originals stay untouched. Copies go to images/opt/<same path>.webp and every page/CSS
reference is pointed at the copy. Run again after adding or replacing a big image:

    python tools/optimize_images.py

Images larger than MIN_KB are resized (longest side) and saved as WebP. Files the
working tree has changed but not committed are read from the last commit instead,
so unreviewed local edits are not published by accident.
"""

import glob
import io
import os
import re
import subprocess
import sys
import urllib.parse

from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

MIN_KB = 120
MAX_SIDE = {"hero": 1600, "default": 1280}
MOBILE_SIDE = 820  # extra small copy for CSS backgrounds on phones
QUALITY = 74
SKIP = ("images/opt/", "images/seo/", "images/favicon/")
PAGES = sorted(glob.glob("*.html"))
CSS = sorted(glob.glob("css/*.css"))
IMG_RE = re.compile(r"images/[^\"'()\s?#]+?\.(?:webp|jpe?g|png)", re.I)


def changed_in_worktree(path):
    out = subprocess.run(["git", "status", "--porcelain", "--", path], capture_output=True, text=True)
    return out.stdout.strip().startswith("M")


def load(path):
    if changed_in_worktree(path):
        data = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True).stdout
        return Image.open(io.BytesIO(data))
    return Image.open(path)


def opt_path(path, suffix=""):
    base, _ = os.path.splitext(path)
    return "images/opt/" + base[len("images/"):] + suffix + ".webp"


def save(img, dest, side):
    img = ImageOps.exif_transpose(img)
    img.thumbnail((side, side), Image.LANCZOS)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    img.save(dest, "WEBP", quality=QUALITY, method=6)
    return os.path.getsize(dest)


def main():
    texts = {f: open(f, encoding="utf-8").read() for f in PAGES + CSS}
    refs = {}
    css_refs = {urllib.parse.unquote(m) for f in CSS for m in IMG_RE.findall(texts[f])}
    for f, s in texts.items():
        for m in IMG_RE.findall(s):
            # CSS references are relative to css/ ("../images/...").
            real = urllib.parse.unquote(m)
            if real.startswith(SKIP) or not os.path.exists(real):
                continue
            if os.path.getsize(real) // 1024 >= MIN_KB:
                refs.setdefault(real, set()).add(m)

    before = after = 0
    mapping = {}
    for real, spellings in sorted(refs.items()):
        side = MAX_SIDE["hero"] if "/hero/" in real else MAX_SIDE["default"]
        dest = opt_path(real)
        size = save(load(real), dest, side)
        if real in css_refs:  # CSS backgrounds also get a phone-size copy (see css/shop.css)
            save(load(real), opt_path(real, "-m"), MOBILE_SIDE)
        before += os.path.getsize(real)
        after += size
        for sp in spellings:
            mapping[sp] = urllib.parse.quote(dest) if "%20" in sp else dest
        print(f"{os.path.getsize(real) // 1024:6d}KB -> {size // 1024:5d}KB  {real}")

    for f, s in texts.items():
        new = s
        for old, dest in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
            new = re.sub(re.escape(old) + r"(?![\w%.-])", dest, new)
        # Zoom links (lightbox) keep the full-size original so small text stays readable.
        for old, dest in mapping.items():
            new = new.replace(f'<a href="{dest}"', f'<a href="{old}"')
        if new != s:
            open(f, "w", encoding="utf-8").write(new)
            print("updated", f)
    print(f"total {before // 1024}KB -> {after // 1024}KB")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
