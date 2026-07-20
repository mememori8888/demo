#!/usr/bin/env python3
"""Enrich review CSV relevance ranks by local Google Maps scraping.

Desktop-only replacement for scripts/enrich_review_relevance_ranks.py.
It reuses a logged-in Chromium profile and matches relevance order by レビューGID.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
import glob
import html
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, unquote, urlparse

from playwright.async_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


FIELDNAMES = [
    "レビューID",
    "施設ID",
    "施設GID",
    "レビュワー評価",
    "レビュワー名",
    "レビュー日時",
    "レビュー本文",
    "オーナー返信",
    "レビュー表示順位",
    "レビュー取得ソート",
    "関連度ランク",
    "関連度取得ソート",
    "関連度取得日時",
    "レビュー要約",
    "レビューGID",
]

REVIEW_CARD_SELECTOR = ".jftiEf[data-review-id], [data-review-id]"
RELEVANCE_SORT = "qualityScore"
WRITE_REVIEW_EXCLUDE = r"クチコミを書く|口コミを書く|レビューを書く|投稿|Write a review"


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def read_rows(path: str | Path) -> list[dict[str, str]]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSVファイルが見つかりません: {path}")
    if path.stat().st_size == 0:
        return []
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp932", "shift_jis"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"CSVを読み込めませんでした: {path}")


def read_fieldnames(path: str | Path) -> list[str]:
    path = Path(path)
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp932", "shift_jis"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle).fieldnames or [])
        except UnicodeDecodeError:
            continue
    raise ValueError(f"CSVヘッダーを読み込めませんでした: {path}")


def output_fieldnames(input_fieldnames: list[str]) -> list[str]:
    fieldnames = list(input_fieldnames)
    for column in FIELDNAMES:
        if column not in fieldnames:
            fieldnames.append(column)
    return fieldnames


def write_rows(path: str | Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: (row.get(column) or "").strip() for column in (fieldnames or FIELDNAMES)})


def maps_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return value
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(value)}"


def detect_fid(row: dict[str, str]) -> str:
    for column in ("施設FID", "FID", "fid", "Facility FID", "facility_fid"):
        value = (row.get(column) or "").strip()
        if re.match(r"^0x[0-9a-f]+:0x[0-9a-f]+$", value, re.IGNORECASE):
            return value

    url = html.unescape((row.get("GoogleMap") or row.get("googlemap") or "").strip())
    if not url:
        return ""
    decoded = unquote(url)
    match = re.search(r"!1s([^!/?&]+)", decoded)
    if match:
        return match.group(1)
    match = re.search(r"(0x[0-9a-f]+:0x[0-9a-f]+)", decoded, re.IGNORECASE)
    return match.group(1) if match else ""


def load_facilities(path: str | Path) -> dict[str, dict[str, str]]:
    facilities: dict[str, dict[str, str]] = {}
    for row in read_rows(path):
        facility_id = (row.get("施設ID") or row.get("post_id") or row.get("ID") or "").strip()
        post_id = (row.get("post_id") or "").strip()
        row_id = (row.get("ID") or "").strip()
        facility_gid = (row.get("施設GID") or row.get("GID") or row.get("gid") or "").strip()
        google_map = (row.get("GoogleMap") or row.get("googlemap") or "").strip()
        facility = {
            "facility_id": facility_id,
            "facility_gid": facility_gid,
            "facility_name": (row.get("施設名") or "").strip(),
            "fid": detect_fid(row),
            "google_map": google_map,
        }
        for key in (facility_gid, facility_id, post_id, row_id):
            if key and key not in facilities:
                facilities[key] = facility
    return facilities


def fallback_facility_from_key(key: str) -> dict[str, str] | None:
    if re.match(r"^ChIJ[A-Za-z0-9_-]+$", key):
        return {
            "facility_id": key,
            "facility_gid": key,
            "facility_name": key,
            "fid": "",
            "google_map": key,
        }
    return None


def load_recent_review_facilities(patterns: list[str]) -> tuple[set[str], set[str], list[str]]:
    facility_keys: set[str] = set()
    review_gids: set[str] = set()
    files: list[str] = []
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if not matches:
            raise FileNotFoundError(f"--recent-review-glob に一致するCSVがありません: {pattern}")
        files.extend(matches)

    for filename in files:
        for row in read_rows(filename):
            facility_gid = (row.get("施設GID") or "").strip()
            facility_id = (row.get("施設ID") or "").strip()
            review_gid = (row.get("レビューGID") or "").strip()
            if facility_gid:
                facility_keys.add(facility_gid)
            elif facility_id:
                facility_keys.add(facility_id)
            if review_gid:
                review_gids.add(review_gid)
    return facility_keys, review_gids, files


async def click_first_visible(page: Page, pattern: str, timeout_ms: int = 1500) -> bool:
    regex = re.compile(pattern, re.IGNORECASE)
    locators = [
        page.get_by_role("button", name=regex),
        page.get_by_role("tab", name=regex),
        page.get_by_text(regex),
    ]
    for locator in locators:
        try:
            first = locator.first
            await first.wait_for(state="visible", timeout=timeout_ms)
            await first.click(timeout=timeout_ms)
            return True
        except Exception:
            continue
    return False


async def click_text_in_page(page: Page, pattern: str, exclude_pattern: str | None = None) -> bool:
    return bool(
        await page.evaluate(
            """
            ([pattern, excludePattern]) => {
                const regex = new RegExp(pattern, "i");
                const excludeRegex = excludePattern ? new RegExp(excludePattern, "i") : null;
                const candidates = [
                    ...document.querySelectorAll("button"),
                    ...document.querySelectorAll("[role='button']"),
                    ...document.querySelectorAll("[role='tab']"),
                    ...document.querySelectorAll("a"),
                ];
                const target = candidates.find((el) => {
                    const text = [
                        el.innerText || "",
                        el.getAttribute("aria-label") || "",
                        el.getAttribute("title") || "",
                    ].join(" ");
                    return regex.test(text) && !(excludeRegex && excludeRegex.test(text));
                });
                if (!target) return false;
                target.scrollIntoView({ block: "center", inline: "center" });
                target.click();
                return true;
            }
            """,
            [pattern, exclude_pattern],
        )
    )


async def close_write_review_dialog_if_present(page: Page) -> bool:
    is_open = await page.evaluate(
        r"""
        () => {
            const dialog = document.querySelector("[role='dialog']");
            if (!dialog) return false;
            const text = dialog.innerText || "";
            return /この場所での自分の体験|感想を共有|投稿|Write a review|Share details/i.test(text);
        }
        """
    )
    if not is_open:
        return False
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(500)
    if await page.locator("[role='dialog']").count() > 0:
        await click_text_in_page(page, r"閉じる|Close")
        await page.wait_for_timeout(500)
    return True


async def accept_consent_if_present(page: Page) -> None:
    await click_first_visible(page, r"すべて同意|同意する|Accept all|I agree", timeout_ms=1200)


async def open_first_place_if_search_results(page: Page) -> None:
    if "/maps/search" not in page.url:
        return
    clicked = await page.evaluate(
        """
        () => {
            const result = document.querySelector("a[href*='/maps/place/']");
            if (!result) return false;
            result.click();
            return true;
        }
        """
    )
    if clicked:
        await page.wait_for_timeout(2500)


async def open_reviews(page: Page) -> None:
    await close_write_review_dialog_if_present(page)
    if await page.locator("div[role='feed']").count() > 0:
        return

    tab_regex = re.compile(r"クチコミ|口コミ|レビュー|reviews?", re.IGNORECASE)
    opened = False
    for locator in (
        page.get_by_role("tab", name=tab_regex),
        page.locator("[role='tab']").filter(has_text=tab_regex),
        page.locator("button").filter(has_text=tab_regex),
    ):
        try:
            await locator.first.wait_for(state="visible", timeout=2500)
            await locator.first.click(timeout=2500)
            opened = True
            break
        except Exception:
            continue

    if opened and await close_write_review_dialog_if_present(page):
        opened = False
    if not opened:
        opened = await click_text_in_page(page, r"クチコミ|口コミ|レビュー|reviews?", WRITE_REVIEW_EXCLUDE)
        if opened and await close_write_review_dialog_if_present(page):
            opened = False
    if not opened:
        await page.keyboard.press("Escape")
        opened = await click_text_in_page(page, r"\d+(\.\d+)?\s*(件|reviews?)", WRITE_REVIEW_EXCLUDE)
        if opened and await close_write_review_dialog_if_present(page):
            opened = False

    await page.wait_for_timeout(1200)
    if await page.locator("div[role='feed']").count() == 0:
        clicked_more_reviews = False
        for locator in (
            page.locator("button").filter(has_text=re.compile(r"その他のクチコミ|More reviews|See all reviews", re.IGNORECASE)),
            page.get_by_text(re.compile(r"その他のクチコミ|More reviews|See all reviews", re.IGNORECASE)),
        ):
            try:
                await locator.first.scroll_into_view_if_needed(timeout=2500)
                await locator.first.click(timeout=2500)
                clicked_more_reviews = True
                break
            except Exception:
                continue
        if not clicked_more_reviews:
            await click_text_in_page(page, r"その他のクチコミ|More reviews|See all reviews", WRITE_REVIEW_EXCLUDE)
        await page.wait_for_timeout(1800)

    try:
        await page.wait_for_selector(REVIEW_CARD_SELECTOR, timeout=10000)
    except PlaywrightTimeoutError:
        raise RuntimeError("レビュー一覧を開けませんでした。レビューカードが見つかりません。")

    gids = await extract_review_gids(page)
    if "!9m1!1b1" not in page.url and len(gids) <= 3:
        raise RuntimeError("レビュー一覧を開けませんでした。概要欄のレビュー抜粋で止まっています。")


async def select_relevance_sort(page: Page) -> None:
    sort_button_pattern = r"並べ替え|並び替え|クチコミの並べ替え|Sort"
    relevance_pattern = r"関連性の高い順|関連度順|Most relevant"

    opened = False
    for locator in (
        page.get_by_role("button", name=re.compile(sort_button_pattern, re.IGNORECASE)),
        page.locator("button").filter(has_text=re.compile(sort_button_pattern, re.IGNORECASE)),
    ):
        try:
            await locator.first.wait_for(state="visible", timeout=2500)
            await locator.first.scroll_into_view_if_needed(timeout=2500)
            await locator.first.click(timeout=2500)
            opened = True
            break
        except Exception:
            continue
    if not opened:
        opened = await click_text_in_page(page, sort_button_pattern)
    if not opened:
        raise RuntimeError("クチコミの並べ替えボタンをクリックできませんでした")

    await page.wait_for_timeout(600)
    selected = False
    for locator in (
        page.get_by_role("menuitemradio", name=re.compile(relevance_pattern, re.IGNORECASE)),
        page.get_by_role("menuitem", name=re.compile(relevance_pattern, re.IGNORECASE)),
        page.get_by_text(re.compile(relevance_pattern, re.IGNORECASE)),
    ):
        try:
            await locator.first.wait_for(state="visible", timeout=2500)
            await locator.first.click(timeout=2500)
            selected = True
            break
        except Exception:
            continue
    if not selected:
        selected = await click_text_in_page(page, relevance_pattern)
    if not selected:
        raise RuntimeError("関連性の高い順をクリックできませんでした")
    await page.wait_for_timeout(1200)


async def scroll_reviews(page: Page, target_count: int, max_scrolls: int) -> None:
    previous_count = 0
    previous_scroll_top = -1
    previous_scroll_height = -1
    stalled = 0
    for _ in range(max_scrolls):
        state = await page.evaluate(
            """
            () => {
                const feed = document.querySelector("div[role='feed']");
                if (feed) {
                    feed.scrollBy(0, Math.max(feed.clientHeight, 700));
                    return { scrollTop: feed.scrollTop, scrollHeight: feed.scrollHeight };
                }
                const cards = [...document.querySelectorAll(".jftiEf[data-review-id], [data-review-id]")];
                const reviewScroller = [...document.querySelectorAll("div")]
                    .filter((el) => el.querySelectorAll("[data-review-id]").length > 0 && el.scrollHeight > el.clientHeight + 50)
                    .sort((a, b) => {
                        const reviewDiff = b.querySelectorAll("[data-review-id]").length - a.querySelectorAll("[data-review-id]").length;
                        if (reviewDiff) return reviewDiff;
                        return (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight);
                    })[0];
                if (reviewScroller) {
                    reviewScroller.scrollBy(0, Math.max(reviewScroller.clientHeight, 800));
                    return { scrollTop: reviewScroller.scrollTop, scrollHeight: reviewScroller.scrollHeight };
                }
                const last = cards[cards.length - 1];
                if (last) last.scrollIntoView({ block: "end" });
                else window.scrollBy(0, 900);
                return { scrollTop: window.scrollY, scrollHeight: document.documentElement.scrollHeight };
            }
            """
        )
        await page.wait_for_timeout(900)
        current_count = await page.locator(REVIEW_CARD_SELECTOR).count()
        if current_count >= target_count:
            return
        scroll_top = state.get("scrollTop") if isinstance(state, dict) else None
        scroll_height = state.get("scrollHeight") if isinstance(state, dict) else None
        if current_count == previous_count and scroll_top == previous_scroll_top and scroll_height == previous_scroll_height:
            stalled += 1
            if stalled >= 4:
                return
        else:
            stalled = 0
        previous_count = current_count
        previous_scroll_top = scroll_top
        previous_scroll_height = scroll_height


async def scroll_review_container_once(page: Page) -> dict[str, Any]:
    state = await page.evaluate(
        """
        () => {
            const feed = document.querySelector("div[role='feed']");
            const scroller = feed || [...document.querySelectorAll("div")]
                .filter((el) => el.querySelectorAll("[data-review-id]").length > 0 && el.scrollHeight > el.clientHeight + 50)
                .sort((a, b) => {
                    const reviewDiff = b.querySelectorAll("[data-review-id]").length - a.querySelectorAll("[data-review-id]").length;
                    if (reviewDiff) return reviewDiff;
                    return (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight);
                })[0];
            if (scroller) {
                const before = scroller.scrollTop;
                scroller.scrollBy(0, Math.max(scroller.clientHeight * 0.85, 700));
                return {
                    found: true,
                    before,
                    after: scroller.scrollTop,
                    scrollHeight: scroller.scrollHeight,
                    clientHeight: scroller.clientHeight,
                };
            }
            window.scrollBy(0, 900);
            return {
                found: false,
                before: window.scrollY,
                after: window.scrollY,
                scrollHeight: document.documentElement.scrollHeight,
                clientHeight: window.innerHeight,
            };
        }
        """
    )
    await page.mouse.move(276, 650)
    await page.mouse.wheel(0, 900)
    return state


async def reset_review_scroll(page: Page) -> None:
    await page.evaluate(
        """
        () => {
            const feed = document.querySelector("div[role='feed']");
            const scroller = feed || [...document.querySelectorAll("div")]
                .filter((el) => el.querySelectorAll("[data-review-id]").length > 0 && el.scrollHeight > el.clientHeight + 50)
                .sort((a, b) => {
                    const reviewDiff = b.querySelectorAll("[data-review-id]").length - a.querySelectorAll("[data-review-id]").length;
                    if (reviewDiff) return reviewDiff;
                    return (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight);
                })[0];
            if (scroller) scroller.scrollTop = 0;
        }
        """
    )
    await page.wait_for_timeout(900)


async def extract_review_gids(page: Page) -> list[str]:
    gids = await page.evaluate(
        """
        () => [...document.querySelectorAll(".jftiEf[data-review-id], [data-review-id]")]
            .map((card) => card.getAttribute("data-review-id") || "")
            .filter(Boolean)
        """
    )
    unique: list[str] = []
    seen: set[str] = set()
    for gid in gids:
        if gid not in seen:
            seen.add(gid)
            unique.append(gid)
    return unique


async def extract_review_card_details(page: Page) -> dict[str, dict[str, str]]:
    cards = await page.evaluate(
        """
        () => {
            const parseRating = (card) => {
                const candidates = [
                    ...card.querySelectorAll("[aria-label]"),
                    card,
                ];
                for (const el of candidates) {
                    const label = el.getAttribute("aria-label") || "";
                    const match = label.match(/([0-5](?:[.,]\\d)?)\\s*(?:つ星|星|stars?|スター)/i);
                    if (match) return match[1].replace(",", ".");
                }
                return "";
            };
            const parseDate = (card) => {
                const dateSelectors = [
                    ".rsqaWe",
                    "[class*='rsqaWe']",
                    "[aria-label*='前']",
                    "[aria-label*='ago']",
                    "[aria-label*='編集']",
                    "[aria-label*='Edited']",
                ];
                for (const selector of dateSelectors) {
                    for (const el of card.querySelectorAll(selector)) {
                        const text = (el.innerText || el.textContent || el.getAttribute("aria-label") || "").trim();
                        if (/\\d+\\s*(分|時間|日|週間|か月|年)前|ago|最終編集|Edited|\\d{4}[\\/年-]\\d{1,2}/i.test(text)) {
                            return text;
                        }
                    }
                }
                for (const line of (card.innerText || "").split("\\n").map((line) => line.trim())) {
                    if (/\\d+\\s*(分|時間|日|週間|か月|年)前|ago|最終編集|Edited|\\d{4}[\\/年-]\\d{1,2}/i.test(line)) {
                        return line;
                    }
                }
                return "";
            };
            const details = {};
            for (const card of document.querySelectorAll(".jftiEf[data-review-id], [data-review-id]")) {
                const gid = card.getAttribute("data-review-id") || "";
                if (!gid || details[gid]) continue;
                details[gid] = {
                    reviewer: card.getAttribute("aria-label") || "",
                    rating: parseRating(card),
                    date: parseDate(card),
                    text: (card.innerText || "").trim(),
                };
            }
            return details;
        }
        """
    )
    return {
        gid: {
            "reviewer": str(detail.get("reviewer") or "").strip(),
            "rating": str(detail.get("rating") or "").strip(),
            "date": str(detail.get("date") or "").strip(),
            "text": str(detail.get("text") or "").strip(),
        }
        for gid, detail in cards.items()
    }


async def collect_review_gids_with_scroll(page: Page, target_count: int, max_scrolls: int) -> tuple[list[str], dict[str, dict[str, str]]]:
    collected: list[str] = []
    details: dict[str, dict[str, str]] = {}
    seen: set[str] = set()
    previous_total = 0
    stalled = 0

    for _ in range(max_scrolls + 1):
        details.update(await extract_review_card_details(page))
        for gid in await extract_review_gids(page):
            if gid not in seen:
                seen.add(gid)
                collected.append(gid)
        if len(collected) >= target_count:
            return collected[:target_count], details

        state = await scroll_review_container_once(page)
        await page.wait_for_timeout(800)

        scrolled = not isinstance(state, dict) or state.get("after") != state.get("before")
        if len(collected) == previous_total and not scrolled:
            stalled += 1
            if stalled >= 5:
                break
        else:
            stalled = 0
        previous_total = len(collected)

    details.update(await extract_review_card_details(page))
    return collected[:target_count], details


async def fetch_relevance_gids_on_page(
    page: Page,
    facility: dict[str, str],
    rank_limit: int,
    max_scrolls: int,
    force_sort_click: bool,
) -> tuple[list[str], dict[str, dict[str, str]]]:
    target = facility.get("google_map") or facility.get("facility_name") or facility.get("facility_gid") or facility.get("facility_id")
    if not target:
        raise RuntimeError("GoogleMap URLまたは施設名がありません")
    await page.goto(maps_url(target), wait_until="domcontentloaded", timeout=60000)
    await accept_consent_if_present(page)
    await open_first_place_if_search_results(page)
    await open_reviews(page)
    if force_sort_click:
        await select_relevance_sort(page)
    await reset_review_scroll(page)
    gids, details = await collect_review_gids_with_scroll(page, rank_limit, max_scrolls)
    await close_write_review_dialog_if_present(page)
    if not gids:
        raise RuntimeError(f"関連度レビュー0件: title={await page.title()!r} url={page.url}")
    return gids[:rank_limit], details


async def fetch_rank_maps(
    facilities: list[dict[str, str]],
    profile_dir: Path,
    rank_limit: int,
    max_scrolls: int,
    timeout: int,
    headless: bool,
    slow_mo: int,
    force_sort_click: bool,
    on_result: Any | None = None,
    on_failure: Any | None = None,
    stop_on_failure: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rank_maps: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    async with async_playwright() as p:
        launch_options = {
            "user_data_dir": str(profile_dir.resolve()),
            "headless": headless,
            "slow_mo": slow_mo,
            "locale": "ja",
            "extra_http_headers": {"Accept-Language": "ja,en;q=0.7"},
            "viewport": {"width": 1366, "height": 900},
        }
        try:
            context = await p.chromium.launch_persistent_context(channel="chrome", **launch_options)
        except Exception as chrome_exc:
            print(f"Chrome channel launch failed, fallback to bundled Chromium: {chrome_exc}", flush=True)
            context = await p.chromium.launch_persistent_context(**launch_options)
        page = await context.new_page()
        try:
            for index, facility in enumerate(facilities, start=1):
                label = f"{facility.get('facility_id')} {facility.get('facility_name')}"
                print(f"[{index}/{len(facilities)}] {label} 関連度取得中", flush=True)
                try:
                    gids, details = await asyncio.wait_for(
                        fetch_relevance_gids_on_page(page, facility, rank_limit, max_scrolls, force_sort_click),
                        timeout=timeout,
                    )
                    ranks = {gid: rank for rank, gid in enumerate(gids, start=1)}
                    rank_maps.append({
                        "facility": facility,
                        "ranks": ranks,
                        "details": details,
                        "request_count": 1,
                        "top_count": len(gids),
                    })
                    if on_result:
                        on_result(rank_maps[-1])
                    print(f"  -> top={len(gids)}", flush=True)
                except Exception as exc:
                    failed_item = {"facility": facility, "error": str(exc)}
                    failed.append(failed_item)
                    if on_failure:
                        on_failure(failed_item)
                    print(f"  -> NG: {exc}", flush=True)
                    if stop_on_failure:
                        raise
        finally:
            await context.close()
    return rank_maps, failed


def enrich_review_file(
    review_file: str | Path,
    output_file: str | Path,
    target_facilities: list[dict[str, str]],
    rank_maps: list[dict[str, Any]],
    fetched_at: str,
) -> tuple[int, int, int]:
    fieldnames = output_fieldnames(read_fieldnames(review_file))
    rows = read_rows(review_file)
    for row in rows:
        for column in FIELDNAMES:
            row.setdefault(column, "")

    targeted_gid_or_id: set[str] = set()
    for facility in target_facilities:
        if facility.get("facility_gid"):
            targeted_gid_or_id.add(facility["facility_gid"])
        if facility.get("facility_id"):
            targeted_gid_or_id.add(facility["facility_id"])

    for row in rows:
        facility_key = (row.get("施設GID") or row.get("施設ID") or "").strip()
        if facility_key in targeted_gid_or_id:
            row["関連度ランク"] = ""
            row["関連度取得ソート"] = ""
            row["関連度取得日時"] = ""

    rank_by_gid: dict[str, list[dict[str, str | int]]] = {}
    for result in rank_maps:
        facility = result["facility"]
        for gid, rank in result["ranks"].items():
            rank_by_gid.setdefault(gid, []).append({
                "rank": rank,
                "facility_id": facility.get("facility_id", ""),
                "facility_gid": facility.get("facility_gid", ""),
            })

    matched = 0
    for row in rows:
        gid = (row.get("レビューGID") or "").strip()
        facility_id = (row.get("施設ID") or "").strip()
        facility_gid = (row.get("施設GID") or "").strip()
        rank_match = next(
            (
                item
                for item in rank_by_gid.get(gid, [])
                if (facility_gid and facility_gid == item.get("facility_gid"))
                or (facility_id and facility_id == item.get("facility_id"))
            ),
            None,
        )
        if rank_match:
            row["関連度ランク"] = str(rank_match["rank"])
            row["関連度取得ソート"] = RELEVANCE_SORT
            row["関連度取得日時"] = fetched_at
            matched += 1

    write_rows(output_file, rows, fieldnames)
    return matched, len(rows), sum(len(items) for items in rank_by_gid.values())


def initialize_output_file(review_file: str | Path, output_file: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    fieldnames = output_fieldnames(read_fieldnames(review_file))
    rows = read_rows(review_file)
    for row in rows:
        for column in FIELDNAMES:
            row.setdefault(column, "")
    write_rows(output_file, rows, fieldnames)
    return rows, fieldnames


def apply_rank_result_to_rows(
    rows: list[dict[str, str]],
    output_file: str | Path,
    fieldnames: list[str],
    facility: dict[str, str],
    ranks: dict[str, int],
    fetched_at: str,
) -> int:
    facility_id = (facility.get("facility_id") or "").strip()
    facility_gid = (facility.get("facility_gid") or "").strip()
    matched = 0

    for row in rows:
        row_facility_id = (row.get("施設ID") or "").strip()
        row_facility_gid = (row.get("施設GID") or "").strip()
        same_facility = (facility_gid and row_facility_gid == facility_gid) or (facility_id and row_facility_id == facility_id)
        if not same_facility:
            continue
        row["関連度ランク"] = ""
        row["関連度取得ソート"] = ""
        row["関連度取得日時"] = ""

    for row in rows:
        row_facility_id = (row.get("施設ID") or "").strip()
        row_facility_gid = (row.get("施設GID") or "").strip()
        same_facility = (facility_gid and row_facility_gid == facility_gid) or (facility_id and row_facility_id == facility_id)
        if not same_facility:
            continue
        gid = (row.get("レビューGID") or "").strip()
        if gid in ranks:
            row["関連度ランク"] = str(ranks[gid])
            row["関連度取得ソート"] = RELEVANCE_SORT
            row["関連度取得日時"] = fetched_at
            matched += 1

    write_rows(output_file, rows, fieldnames)
    return matched


def clear_relevance_for_facilities(rows: list[dict[str, str]], facilities: list[dict[str, str]]) -> None:
    targeted_gid_or_id: set[str] = set()
    for facility in facilities:
        if facility.get("facility_gid"):
            targeted_gid_or_id.add(facility["facility_gid"])
        if facility.get("facility_id"):
            targeted_gid_or_id.add(facility["facility_id"])

    for row in rows:
        facility_key = (row.get("施設GID") or row.get("施設ID") or "").strip()
        if facility_key in targeted_gid_or_id:
            row["関連度ランク"] = ""
            row["関連度取得ソート"] = ""
            row["関連度取得日時"] = ""


def write_summary(
    path: str | Path,
    rank_maps: list[dict[str, Any]],
    recent_review_gids: set[str],
    matched: int,
    total_rows: int,
    failed: list[dict[str, Any]],
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "施設ID",
                "施設GID",
                "施設名",
                "関連度取得件数",
                "期間内レビュー上位10一致数",
                "エラー",
            ],
        )
        writer.writeheader()
        for result in rank_maps:
            facility = result["facility"]
            recent_matches = sum(1 for gid in result["ranks"] if gid in recent_review_gids)
            writer.writerow({
                "施設ID": facility.get("facility_id", ""),
                "施設GID": facility.get("facility_gid", ""),
                "施設名": facility.get("facility_name", ""),
                "関連度取得件数": result.get("top_count", 0),
                "期間内レビュー上位10一致数": recent_matches,
                "エラー": "",
            })
        for item in failed:
            facility = item["facility"]
            writer.writerow({
                "施設ID": facility.get("facility_id", ""),
                "施設GID": facility.get("facility_gid", ""),
                "施設名": facility.get("facility_name", ""),
                "関連度取得件数": 0,
                "期間内レビュー上位10一致数": 0,
                "エラー": item["error"],
            })
    print(f"Summary: {path}")
    print(f"Review rows: {total_rows}, matched relevance ranks: {matched}, failed facilities: {len(failed)}")


def has_visible_review_body(card_text: str) -> bool:
    ignored = {
        "新規",
        "高評価",
        "共有",
        "もっと見る",
    }
    for line in (line.strip() for line in card_text.splitlines()):
        if not line or line in ignored:
            continue
        if re.fullmatch(r"[\s]+", line):
            continue
        if re.search(r"(\d+\s*(分|時間|日|週間|か月|年)前|Edited|ago|最終編集)", line):
            continue
        if "件のクチコミ" in line or "ローカルガイド" in line or "枚の写真" in line:
            continue
        if len(line) >= 12:
            return True
    return False


def write_rank_detail(path: str | Path, rank_maps: list[dict[str, Any]], review_file: str | Path) -> None:
    rows = read_rows(review_file)
    reviews_by_gid: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        gid = (row.get("レビューGID") or "").strip()
        if gid:
            reviews_by_gid.setdefault(gid, []).append(row)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "取得施設ID",
                "取得施設GID",
                "取得施設名",
                "関連度ランク",
                "取得レビューGID",
                "取得レビュワー名",
                "取得レビュワー評価",
                "取得レビュー日時",
                "取得カード本文",
                "取得カード本文あり",
                "一致レビュー数",
                "一致施設ID",
                "一致施設GID",
                "一致レビュワー名",
                "一致レビュー日時",
                "一致レビュー本文",
            ],
        )
        writer.writeheader()
        for result in rank_maps:
            facility = result["facility"]
            details = result.get("details") or {}
            for gid, rank in sorted(result["ranks"].items(), key=lambda item: item[1]):
                current = details.get(gid, {})
                current_text = current.get("text", "")
                matches = reviews_by_gid.get(gid, [])
                if matches:
                    for match in matches:
                        writer.writerow({
                            "取得施設ID": facility.get("facility_id", ""),
                            "取得施設GID": facility.get("facility_gid", ""),
                            "取得施設名": facility.get("facility_name", ""),
                            "関連度ランク": rank,
                            "取得レビューGID": gid,
                            "取得レビュワー名": current.get("reviewer", ""),
                            "取得レビュワー評価": current.get("rating", ""),
                            "取得レビュー日時": current.get("date", ""),
                            "取得カード本文": current_text,
                            "取得カード本文あり": "1" if has_visible_review_body(current_text) else "0",
                            "一致レビュー数": len(matches),
                            "一致施設ID": match.get("施設ID", ""),
                            "一致施設GID": match.get("施設GID", ""),
                            "一致レビュワー名": match.get("レビュワー名", ""),
                            "一致レビュー日時": match.get("レビュー日時", ""),
                            "一致レビュー本文": match.get("レビュー本文", ""),
                        })
                else:
                    writer.writerow({
                        "取得施設ID": facility.get("facility_id", ""),
                        "取得施設GID": facility.get("facility_gid", ""),
                        "取得施設名": facility.get("facility_name", ""),
                        "関連度ランク": rank,
                        "取得レビューGID": gid,
                        "取得レビュワー名": current.get("reviewer", ""),
                        "取得レビュワー評価": current.get("rating", ""),
                        "取得レビュー日時": current.get("date", ""),
                        "取得カード本文": current_text,
                        "取得カード本文あり": "1" if has_visible_review_body(current_text) else "0",
                        "一致レビュー数": 0,
                        "一致施設ID": "",
                        "一致施設GID": "",
                        "一致レビュワー名": "",
                        "一致レビュー日時": "",
                        "一致レビュー本文": "",
                    })
    print(f"Rank detail: {path}")


def write_unmatched_reviews(path: str | Path, rank_maps: list[dict[str, Any]], review_file: str | Path) -> None:
    rows = read_rows(review_file)
    known_gids = {
        (row.get("レビューGID") or "").strip()
        for row in rows
        if (row.get("レビューGID") or "").strip()
    }

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for result in rank_maps:
            facility = result["facility"]
            details = result.get("details") or {}
            for gid, rank in sorted(result["ranks"].items(), key=lambda item: item[1]):
                if gid in known_gids:
                    continue
                current = details.get(gid, {})
                writer.writerow({
                    "レビューID": "",
                    "施設ID": facility.get("facility_id", ""),
                    "施設GID": facility.get("facility_gid", ""),
                    "レビュワー評価": current.get("rating", ""),
                    "レビュワー名": current.get("reviewer", ""),
                    "レビュー日時": current.get("date", ""),
                    "レビュー本文": current.get("text", ""),
                    "オーナー返信": "",
                    "レビュー表示順位": str(rank),
                    "レビュー取得ソート": RELEVANCE_SORT,
                    "関連度ランク": str(rank),
                    "関連度取得ソート": RELEVANCE_SORT,
                    "関連度取得日時": "",
                    "レビュー要約": "",
                    "レビューGID": gid,
                })
    print(f"Unmatched reviews: {path}")


async def async_main(args: argparse.Namespace) -> None:
    target_patterns = args.recent_review_glob or [args.review_file]
    target_keys, target_review_gids, target_files = load_recent_review_facilities(target_patterns)
    print(f"Target review files: {len(target_files)}")
    print(f"Target review rows with GID: {len(target_review_gids)}")
    print(f"Facilities in target reviews: {len(target_keys)}")
    if not target_keys:
        print("対象レビューに施設ID/施設GIDがないため、関連度取得はスキップします。")
        return

    facility_lookup = load_facilities(args.facility_file)
    target_facilities: list[dict[str, str]] = []
    seen: set[str] = set()
    skipped_duplicate_facilities = 0
    skipped_missing_facilities = 0
    fallback_gid_facilities = 0
    for key in sorted(target_keys):
        facility = facility_lookup.get(key) or fallback_facility_from_key(key)
        if facility and key not in facility_lookup:
            fallback_gid_facilities += 1
        dedupe_key = (facility or {}).get("facility_gid") or (facility or {}).get("facility_id")
        if not facility or not dedupe_key:
            skipped_missing_facilities += 1
            continue
        if dedupe_key in seen:
            skipped_duplicate_facilities += 1
            continue
        seen.add(dedupe_key)
        target_facilities.append(facility)

    if args.start > 1:
        target_facilities = target_facilities[args.start - 1 :]
    if args.limit:
        target_facilities = target_facilities[: args.limit]
    if not target_facilities:
        raise SystemExit("期間内レビューのある施設に対応する施設情報が見つかりませんでした。")

    print(f"Facility start: {args.start}")
    print(f"Facilities to query locally: {len(target_facilities)}")
    print(f"Skipped duplicate facilities: {skipped_duplicate_facilities}")
    print(f"Skipped missing facilities: {skipped_missing_facilities}")
    print(f"Fallback GID facilities: {fallback_gid_facilities}")
    print(f"Rank limit: {args.rank_limit}, sort: {RELEVANCE_SORT}")
    print(f"Chromium profile: {args.profile_dir.resolve()}")

    output_file = args.output_file or args.review_file
    output_rows, output_fieldnames = initialize_output_file(args.review_file, output_file)
    clear_relevance_for_facilities(output_rows, target_facilities)
    write_rows(output_file, output_rows, output_fieldnames)
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    processed_rank_maps: list[dict[str, Any]] = []
    failed_items: list[dict[str, Any]] = []
    matched_so_far = 0
    rank_candidates_so_far = 0

    def persist_result(result: dict[str, Any]) -> None:
        nonlocal matched_so_far, rank_candidates_so_far
        processed_rank_maps.append(result)
        rank_candidates_so_far += len(result["ranks"])
        matched = apply_rank_result_to_rows(
            output_rows,
            output_file,
            output_fieldnames,
            result["facility"],
            result["ranks"],
            fetched_at,
        )
        matched_so_far += matched
        write_summary(args.summary_file, processed_rank_maps, target_review_gids, matched_so_far, len(output_rows), failed_items)
        detail_file = args.rank_detail_file or str(Path(args.summary_file).with_name(Path(args.summary_file).stem + "_details.csv"))
        write_rank_detail(detail_file, processed_rank_maps, output_file)
        unmatched_file = args.unmatched_review_file or str(Path(args.summary_file).with_name(Path(args.summary_file).stem + "_unmatched_reviews.csv"))
        write_unmatched_reviews(unmatched_file, processed_rank_maps, output_file)
        print(f"  -> saved: matched={matched}, matched_total={matched_so_far}", flush=True)

    def persist_failure(item: dict[str, Any]) -> None:
        failed_items.append(item)
        write_summary(args.summary_file, processed_rank_maps, target_review_gids, matched_so_far, len(output_rows), failed_items)
        detail_file = args.rank_detail_file or str(Path(args.summary_file).with_name(Path(args.summary_file).stem + "_details.csv"))
        write_rank_detail(detail_file, processed_rank_maps, output_file)
        unmatched_file = args.unmatched_review_file or str(Path(args.summary_file).with_name(Path(args.summary_file).stem + "_unmatched_reviews.csv"))
        write_unmatched_reviews(unmatched_file, processed_rank_maps, output_file)

    rank_maps, failed = await fetch_rank_maps(
        facilities=target_facilities,
        profile_dir=args.profile_dir,
        rank_limit=args.rank_limit,
        max_scrolls=args.max_scrolls,
        timeout=args.timeout,
        headless=args.headless,
        slow_mo=args.slow_mo,
        force_sort_click=args.force_sort_click,
        on_result=persist_result,
        on_failure=persist_failure,
        stop_on_failure=not args.allow_failures,
    )

    matched = matched_so_far
    total_rows = len(output_rows)
    rank_candidates = rank_candidates_so_far
    print(f"Fetched rank candidates: {rank_candidates}")
    print("Only relevance columns were updated.")
    write_summary(args.summary_file, rank_maps, target_review_gids, matched, total_rows, failed)
    detail_file = args.rank_detail_file or str(Path(args.summary_file).with_name(Path(args.summary_file).stem + "_details.csv"))
    write_rank_detail(detail_file, rank_maps, output_file)
    unmatched_file = args.unmatched_review_file or str(Path(args.summary_file).with_name(Path(args.summary_file).stem + "_unmatched_reviews.csv"))
    write_unmatched_reviews(unmatched_file, rank_maps, output_file)

    if failed and not args.allow_failures:
        raise SystemExit(f"ローカル関連度取得に失敗した施設があります: {len(failed)}件")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ローカルGoogle Maps直接スクレイピングで関連度ランクを付与します。")
    parser.add_argument("--review-file", required=True)
    parser.add_argument("--output-file", default=None, help="省略時は --review-file を上書きします")
    parser.add_argument("--facility-file", required=True)
    parser.add_argument("--recent-review-glob", action="append", default=None, help="省略時は --review-file を対象レビューとして使います")
    parser.add_argument("--summary-file", default="results/relevance_rank_summary_local.csv")
    parser.add_argument("--rank-detail-file", default=None)
    parser.add_argument("--unmatched-review-file", default=None)
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument("--rank-limit", type=int, default=10)
    parser.add_argument("--start", type=int, default=1, help="テスト/分割用: 対象施設の開始位置（1始まり）")
    parser.add_argument("--limit", type=int, default=None, help="テスト用: 対象施設数を制限")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-scrolls", type=int, default=14)
    parser.add_argument("--slow-mo", type=int, default=0)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--force-sort-click", action="store_true", help="必要な場合だけ並べ替えメニューから関連性の高い順を明示クリックします")
    parser.add_argument("--allow-failures", action="store_true")
    return parser.parse_args()


def main() -> None:
    configure_stdio()
    args = parse_args()
    if args.rank_limit < 1:
        raise SystemExit("--rank-limit は1以上を指定してください。")
    if args.start < 1:
        raise SystemExit("--start は1以上を指定してください。")
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
