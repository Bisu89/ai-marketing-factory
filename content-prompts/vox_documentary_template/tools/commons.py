"""Wikimedia Commons helper: find archival images and read their REAL licence/author metadata.

Nothing here decides whether an image may be used -- it only reports what Commons says. A human must
still read the licence on the file page before approving the image in the app.

Usage:
  python commons.py "query one" "query two"        # list candidates with licence + size
"""

import html
import json
import re
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "VoxDocumentaryTemplate/1.0 (personal research; set your contact in this header)"}
API = "https://commons.wikimedia.org/w/api.php"
# Licences that need more than "credit the author": a person must read them before approving.
NEEDS_REVIEW = ("CC BY-SA", "FAL", "GFDL", "CC BY-NC", "CC BY-ND")


def _call(**params) -> dict:
    params["format"] = "json"
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=60))


def _plain(s) -> str:
    """Commons metadata values are usually HTML strings but can be numbers/None."""
    return html.unescape(re.sub(r"<[^>]+>", "", "" if s is None else str(s))).strip()


def search(query: str, limit: int = 8) -> list[str]:
    d = _call(action="query", list="search", srsearch=query, srnamespace=6, srlimit=limit)
    return [x["title"] for x in d["query"]["search"]]


def info(title: str, width: int = 1600) -> dict:
    """-> {title, page, url, thumb, width, height, mime, license, artist, needs_review}"""
    d = _call(action="query", titles=title, prop="imageinfo", iiprop="url|size|mime|extmetadata", iiurlwidth=width)
    page = next(iter(d["query"]["pages"].values()))
    if "imageinfo" not in page:
        raise SystemExit(f"Commons has no file called {title!r}")
    ii = page["imageinfo"][0]
    meta = {k: _plain((v or {}).get("value", "")) for k, v in ii.get("extmetadata", {}).items()}
    lic = meta.get("LicenseShortName", "")
    return {
        "title": title, "page": "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_"), "url": ii["url"],
        "thumb": ii.get("thumburl") or ii["url"], "width": ii["width"], "height": ii["height"], "mime": ii["mime"],
        "license": lic, "artist": meta.get("Artist", ""), "needs_review": any(lic.startswith(p) for p in NEEDS_REVIEW) or not lic,
    }


def download(title: str, dest) -> dict:
    meta = info(title)
    req = urllib.request.Request(meta["thumb"], headers=UA)
    with open(dest, "wb") as f:
        f.write(urllib.request.urlopen(req, timeout=180).read())
    return meta


if __name__ == "__main__":
    for q in sys.argv[1:]:
        print("==", q)
        for t in search(q):
            try:
                i = info(t)
                flag = "  <-- READ THE LICENCE" if i["needs_review"] else ""
                print(f"  {t} | {i['license'] or '?'} | {i['width']}x{i['height']}{flag}")
            except SystemExit as e:
                print("  ", t, "ERR", e)
