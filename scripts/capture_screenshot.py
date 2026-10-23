"""Capture the app answering a question, for the README and for social media posts.

The app must already be running (`make run` in another terminal). The script asks the question
through the page like a visitor would, waits for the answer and its citations, then writes:

    docs/screenshots/capture-hd.png        the useful area (header to answer), at 2x
    docs/screenshots/capture-linkedin.png  title and answer card only, fitted to 1200x627 px

With --open-citation, it clicks a cited article instead (the first one, or the one chosen with
--citation) and writes only:

    docs/screenshots/capture-article-hd.png  the page of that article, at 2x

Nothing is written when the app is down, when the language model fails, when the assistant
refuses to answer or when the citation does not open an article: the script says why and exits
with a non-zero status.

Usage
    uv run python scripts/capture_screenshot.py
    uv run python scripts/capture_screenshot.py --question "Qu'est-ce que le NIPU ?"
    uv run python scripts/capture_screenshot.py -q "Qu'est-ce que le NIPU ?" --name nipu \\
        --open-citation --citation 2
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
from playwright.sync_api import Locator, Page, sync_playwright

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
ARTICLE_PATH = re.compile(r"/articles/(\d+)$")


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


def ask(page: Page, base_url: str, question: str) -> Locator:
    """Ask the question in the page. Returns the answer card, which has citations."""
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
    return card


def check_visible_text(page: Page) -> None:
    text = page.locator(".site-header").inner_text() + page.locator("main").inner_text()
    found = find_sensitive(text)
    if found:
        raise CaptureError(f"Donnée sensible visible dans la page : {', '.join(found)}.")


def screenshot_down_to(page: Page, element: Locator) -> bytes:
    """The full width of the page, from the top down to just below `element`."""
    clip = {
        "x": 0,
        "y": 0,
        "width": VIEWPORT["width"],
        "height": element.evaluate(BOTTOM_JS) + BOTTOM_MARGIN,
    }
    return page.screenshot(full_page=True, clip=clip, animations="disabled")


def capture_answer(page: Page, card: Locator) -> tuple[bytes, bytes]:
    """The HD capture and the compact one for the LinkedIn version (PNG)."""
    hide(page, HIDDEN_SELECTORS)
    check_visible_text(page)
    hd_png = screenshot_down_to(page, card)

    hide(page, COMPACT_HIDDEN_SELECTORS)
    column = page.locator("main").evaluate(
        "element => { const r = element.getBoundingClientRect();"
        " return {left: r.left, right: r.right}; }"
    )
    left = max(column["left"] - COMPACT_SIDE_MARGIN, 0)
    right = min(column["right"] + COMPACT_SIDE_MARGIN, VIEWPORT["width"])
    clip = {"x": left, "y": 0, "width": right - left, "height": card.evaluate(BOTTOM_JS)}
    clip["height"] += BOTTOM_MARGIN
    return hd_png, page.screenshot(full_page=True, clip=clip, animations="disabled")


def capture_article(page: Page, card: Locator, position: int) -> bytes:
    """Click the cited article at `position` (1 for the first) and capture its page (PNG)."""
    links = card.locator(".citations a")
    if position > links.count():
        cited = ", ".join(links.all_inner_texts())
        raise CaptureError(
            f"La réponse ne cite que {links.count()} article(s) ({cited}) : "
            f"pas de citation n° {position}."
        )
    link = links.nth(position - 1)
    expected = ARTICLE_PATH.search(link.get_attribute("href") or "")
    if expected is None:
        raise CaptureError("La première citation n'est pas un lien vers un article.")
    number = expected.group(1)

    try:
        with page.expect_navigation(timeout=ANSWER_TIMEOUT_MS) as navigation:
            link.click()
    except PlaywrightError as error:
        raise CaptureError(f"Le clic sur l'article {number} n'a ouvert aucune page.") from error
    response = navigation.value
    opened = ARTICLE_PATH.search(page.url)
    if response is None or not response.ok or opened is None or opened.group(1) != number:
        status = response.status if response else "aucune réponse"
        raise CaptureError(
            f"Le clic sur l'article {number} ne mène pas à sa page ({page.url}, {status})."
        )

    article = page.locator("main article.card")
    if not article.count() or article.locator("h2").inner_text() != f"Article {number}":
        raise CaptureError(f"La page ouverte n'affiche pas l'article {number}.")
    check_visible_text(page)
    return screenshot_down_to(page, article)


def capture(base_url: str, question: str, citation: int | None) -> tuple[bytes, ...]:
    """The HD and compact captures of the answer or, when `citation` is given (1 for the first),
    the capture of that cited article."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context = browser.new_context(
                viewport=VIEWPORT, device_scale_factor=SCALE, color_scheme="light", locale="fr-FR"
            )
            page = context.new_page()
            card = ask(page, base_url, question)
            if citation is not None:
                return (capture_article(page, card, citation),)
            return capture_answer(page, card)
        finally:
            browser.close()


def save_png(png: bytes, path: Path) -> None:
    """Write a capture as a palette PNG: a few hundred KB instead of about a MB.

    Screenshots of text have few distinct colours, so 256 are enough to look identical.
    """
    with Image.open(io.BytesIO(png)) as image:
        image.convert("RGB").quantize(colors=256, dither=Image.Dither.NONE).save(
            path, optimize=True
        )


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
    parser.add_argument(
        "--open-citation",
        action="store_true",
        help="click a cited article and capture its page instead of the answer",
    )
    parser.add_argument(
        "--citation",
        type=int,
        default=1,
        metavar="N",
        help="with --open-citation: which cited article to open (default: 1, the first)",
    )
    args = parser.parse_args()
    if args.citation < 1:
        parser.error("--citation must be 1 or more")

    args.out.mkdir(parents=True, exist_ok=True)
    base_url = args.url.rstrip("/")

    try:
        check_health(base_url)
        pngs = capture(base_url, args.question, args.citation if args.open_citation else None)
    except CaptureError as error:
        print(f"Capture annulée. {error}", file=sys.stderr)
        return 1

    if args.open_citation:
        article_path = args.out / f"{args.name}-article-hd.png"
        save_png(pngs[0], article_path)
        print(f"{article_path} ({article_path.stat().st_size // 1024} Ko)")
        return 0

    hd_png, compact_png = pngs
    hd_path = args.out / f"{args.name}-hd.png"
    linkedin_path = args.out / f"{args.name}-linkedin.png"
    hd_path.write_bytes(hd_png)
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
