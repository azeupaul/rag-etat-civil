"""Capture the app answering a question, for the README and for social media posts.

The app must already be running (`make run` in another terminal). The script asks the question
through the page like a visitor would, waits for the answer and its citations, then writes:

    docs/screenshots/capture-hd.png        the useful area (header to answer), at 2x
    docs/screenshots/capture-linkedin.png  title and answer card only, fitted to 1200x627 px

Nothing is written when the app is down, when the language model fails or when the assistant
refuses to answer: the script says why and exits with a non-zero status.

Usage
    uv run python scripts/capture_screenshot.py
    uv run python scripts/capture_screenshot.py --question "Qu'est-ce que le NIPU ?"
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

DEFAULT_QUESTION = "Dans quel délai doit-on déclarer une naissance ?"
DEFAULT_URL = "http://127.0.0.1:5000"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"

VIEWPORT = {"width": 1200, "height": 700}
SCALE = 2
LINKEDIN_SIZE = (1200, 627)
# The first question loads the embedding model, which can take a while.
ANSWER_TIMEOUT_MS = 120_000
# Space kept under the answer card, in CSS pixels.
BOTTOM_MARGIN = 32

# Text that must never appear in a published image.
SENSITIVE_PATTERNS = {
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    "API key variable": re.compile(r"API_KEY|GEMINI_", re.IGNORECASE),
    "local path": re.compile(r"/home/|/Users/|[A-Z]:\\\\"),
    "local address": re.compile(r"localhost|127\.0\.0\.1|0\.0\.0\.0"),
    "env file": re.compile(r"\.env\b"),
}

# Hidden during the capture only (the app is not modified): the example questions sit between
# the form and the answer and would push the answer down.
HIDDEN_SELECTORS = (".examples",)
# Also hidden for the LinkedIn version, which must stay readable once shrunk to 627 px high:
# the card repeats the question, so the form is not needed to understand the image.
COMPACT_HIDDEN_SELECTORS = (".site-header .lead", ".notice", ".ask-form")
# Space kept on each side of the text column in the LinkedIn version, in CSS pixels.
COMPACT_SIDE_MARGIN = 48


BOTTOM_JS = "element => element.getBoundingClientRect().bottom + window.scrollY"


class CaptureError(Exception):
    """A reason not to produce a screenshot, in words the user can act on."""


def check_health(base_url: str) -> None:
    if not base_url.startswith(("http://", "https://")):
        raise CaptureError(f"URL invalide : {base_url}")
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=5) as response:  # noqa: S310
            health = json.load(response)
    except (urllib.error.URLError, OSError) as error:
        raise CaptureError(
            f"L'application ne répond pas sur {base_url} ({error}).\n"
            "Lancez-la d'abord dans un autre terminal : make run"
        ) from error
    if not health.get("index_ready"):
        raise CaptureError("L'index de recherche est absent : lancez d'abord make index.")


def find_sensitive(text: str) -> list[str]:
    return [name for name, pattern in SENSITIVE_PATTERNS.items() if pattern.search(text)]


def hide(page: Page, selectors: tuple[str, ...]) -> None:
    # Through the CSSOM: the app's CSP blocks injected <style> elements.
    for selector in selectors:
        page.locator(selector).evaluate("element => element.style.display = 'none'")


def capture(base_url: str, question: str, hd_path: Path) -> bytes:
    """Write the HD capture and return the compact one (PNG) for the LinkedIn version."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context = browser.new_context(
                viewport=VIEWPORT, device_scale_factor=SCALE, color_scheme="light", locale="fr-FR"
            )
            page = context.new_page()
            page.goto(base_url)
            page.fill("#question", question)
            page.click(".ask-form button[type=submit]")

            card = page.locator("#result .card")
            try:
                card.wait_for(timeout=ANSWER_TIMEOUT_MS)
            except PlaywrightError as error:
                raise CaptureError(
                    f"Pas de réponse après {ANSWER_TIMEOUT_MS // 1000} s : "
                    "regardez les logs du terminal Flask."
                ) from error

            if page.locator("#result .card-error").count():
                message = page.locator("#result .card-error").inner_text()
                raise CaptureError(
                    f"L'application a renvoyé une erreur : « {message} »\n"
                    "Le plus souvent, l'appel au modèle de langage a échoué : clé GEMINI_API_KEY "
                    "absente ou invalide dans .env, ou quota dépassé. "
                    "La cause exacte est dans les logs du terminal Flask."
                )
            if not page.locator("#result .citations li").count():
                raise CaptureError(
                    "L'assistant n'a pas répondu à cette question (pas de citations) :\n"
                    f"{card.inner_text()}"
                )

            hide(page, HIDDEN_SELECTORS)
            captured_text = (
                page.locator(".site-header").inner_text() + page.locator("main").inner_text()
            )
            found = find_sensitive(captured_text)
            if found:
                raise CaptureError(f"Donnée sensible visible dans la page : {', '.join(found)}.")

            bottom = card.evaluate(BOTTOM_JS)
            clip = {"x": 0, "y": 0, "width": VIEWPORT["width"], "height": bottom + BOTTOM_MARGIN}
            page.screenshot(path=hd_path, full_page=True, clip=clip, animations="disabled")

            hide(page, COMPACT_HIDDEN_SELECTORS)
            column = page.locator("main").evaluate(
                "element => { const r = element.getBoundingClientRect();"
                " return {left: r.left, right: r.right}; }"
            )
            left = max(column["left"] - COMPACT_SIDE_MARGIN, 0)
            right = min(column["right"] + COMPACT_SIDE_MARGIN, VIEWPORT["width"])
            clip = {"x": left, "y": 0, "width": right - left, "height": card.evaluate(BOTTOM_JS)}
            clip["height"] += BOTTOM_MARGIN
            return page.screenshot(full_page=True, clip=clip, animations="disabled")
        finally:
            browser.close()


def make_linkedin(compact_png: bytes, linkedin_path: Path) -> bool:
    """Fit the compact capture into the LinkedIn size. False when it had to be shrunk a lot."""
    target_w, target_h = LINKEDIN_SIZE
    with Image.open(io.BytesIO(compact_png)) as image:
        image = image.convert("RGB")
        ratio = min(target_w / image.width, target_h / image.height)
        resized = image.resize(
            (round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS
        )
        # Background below the content (bottom-left pixel), then the sides are filled by
        # stretching the edge columns, so the white header band and the page colour continue.
        canvas = Image.new("RGB", LINKEDIN_SIZE, resized.getpixel((0, resized.height - 1)))
        x = (target_w - resized.width) // 2
        y = (target_h - resized.height) // 2
        canvas.paste(resized, (x, y))
        if x > 0:
            left = resized.crop((0, 0, 1, resized.height)).resize((x, resized.height))
            right_w = target_w - x - resized.width
            right = resized.crop((resized.width - 1, 0, resized.width, resized.height))
            canvas.paste(left, (0, y))
            canvas.paste(right.resize((right_w, resized.height)), (x + resized.width, y))
        canvas.save(linkedin_path, optimize=True)
    # Below about 60 % of the CSS size the text gets hard to read on a phone.
    return ratio * SCALE >= 0.6


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--question", "-q", default=DEFAULT_QUESTION)
    parser.add_argument("--url", default=DEFAULT_URL, help="where the app runs")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output folder")
    parser.add_argument("--name", default="capture", help="file name prefix")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    hd_path = args.out / f"{args.name}-hd.png"
    linkedin_path = args.out / f"{args.name}-linkedin.png"
    base_url = args.url.rstrip("/")

    try:
        check_health(base_url)
        compact_png = capture(base_url, args.question, hd_path)
    except CaptureError as error:
        print(f"Capture annulée. {error}", file=sys.stderr)
        return 1

    readable = make_linkedin(compact_png, linkedin_path)
    with Image.open(hd_path) as image:
        print(f"{hd_path} ({image.width}x{image.height})")
    print(f"{linkedin_path} ({LINKEDIN_SIZE[0]}x{LINKEDIN_SIZE[1]})")
    if not readable:
        print(
            "Attention : la réponse est longue, le texte est petit dans la version LinkedIn. "
            "Gardez la version HD pour le README et essayez une question à la réponse plus "
            "courte pour LinkedIn.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
