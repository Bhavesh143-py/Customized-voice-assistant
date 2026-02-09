from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    CacheMode,
    CrawlerMonitor,
    MemoryAdaptiveDispatcher,
)

import asyncio
import os
import re
import csv
from urllib.parse import urlparse


# ============================================================
# MAIN CRAWLER PIPELINE (KEEP THIS FIRST FOR PRESENTATION)
# ============================================================

async def crawl_batch():

    browser_config = BrowserConfig(headless=True, verbose=False)

    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        check_robots_txt=False,
        stream=False
    )

    dispatcher = MemoryAdaptiveDispatcher(
        memory_threshold_percent=70.0,
        check_interval=1.0,
        max_session_permit=10,
        monitor=CrawlerMonitor()
    )

    urls = [
        "https://www.pvgcoet.ac.in/pvgcoetgkpim/about-pvgcoetgkpim/",
        "https://www.pvgcoet.ac.in/about-college/campus/",
        "https://www.pvgcoet.ac.in/academics/time-table/",
        "https://www.pvgcoet.ac.in/admission/fe-admission-process/",
        "https://www.pvgcoet.ac.in/admission/fe-admission-contact-details/" , 
        "https://www.pvgcoet.ac.in/students-corner/hostel/" , 
        
    ]

    async with AsyncWebCrawler(config=browser_config) as crawler:

        results = await crawler.arun_many(
            urls=urls,
            config=run_config,
            dispatcher=dispatcher
        )

        for result in results:
            if result.success:
                await process_result(result)
            else:
                print(f"Failed → {result.url} : {result.error_message}")


# ============================================================
# RESULT PROCESSING
# ============================================================

async def process_result(result):

    print(f"\nProcessing: {result.url}")
    print(f"Status Code: {result.status_code}")

    # ---------------- TABLE EXTRACTION ----------------

    if result.tables:

        print(f"\nDetected {len(result.tables)} table(s). Extracting structured data...")

        os.makedirs("scraped_tables", exist_ok=True)

        base_name = generate_filename_from_url(result.url).replace(".txt", "")

        for i, table in enumerate(result.tables, start=1):

            headers = table.get("headers", [])
            rows = table.get("rows", [])

            file_path = f"scraped_tables/{base_name}_table_{i}.csv"

            with open(file_path, "w", newline="", encoding="utf-8") as f:

                writer = csv.writer(f)

                if headers:
                    writer.writerow(headers)

                for row in rows:
                    writer.writerow(row)

            print(f"Saved Table → {file_path}")

    else:
        print("\nNo tables detected.")

    # ---------------- TEXT EXTRACTION ----------------

    if not result.markdown:
        print("No text extracted.")
        return

    text = result.markdown
    lines = text.splitlines()

    cleaned_lines = []

    for line in lines:

        l = line.strip()

        if not l:
            continue

        # Remove markdown links
        if "](" in l:
            continue

        # Remove blacklisted junk
        if contains_blacklisted_keyword(l):
            continue

        cleaned_lines.append(l)

    clean_text = "\n".join(cleaned_lines)

    print("\n--- CLEAN TEXT PREVIEW ---\n")
    print(clean_text[:800])

    save_text_to_file(result.url, clean_text)

    print("-" * 80)


# ============================================================
# FILE SAVE HANDLER
# ============================================================

def save_text_to_file(url, text):

    os.makedirs("scraped_text", exist_ok=True)

    filename = generate_filename_from_url(url)

    filepath = os.path.join("scraped_text", filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"\nSaved → {filepath}")


# ============================================================
# UTILITY FUNCTIONS (PLACED LAST)
# ============================================================

BLACKLIST_KEYWORDS = [
    "skip to content",
    "facebook",
    "twitter",
    "instagram",
    "youtube",
    "linkedin",
    "privacy policy",
    "terms",
    "copyright",
    "login",
    "register",
    "achievements",
    "cookie",
    "all rights reserved",
]


def contains_blacklisted_keyword(line: str) -> bool:
    return any(b in line.lower() for b in BLACKLIST_KEYWORDS)


STOPWORDS_IN_FILENAME = [
    "www",
    "ac",
    "in",
    "about",
    "college",
    "pvgcoet",
]


def generate_filename_from_url(url: str) -> str:

    parsed = urlparse(url)
    path = parsed.path.strip("/")

    if not path:
        return "homepage.txt"

    parts = path.split("/")

    slug = parts[-1] if parts[-1] else parts[-2]
    slug = slug.lower()

    words = re.split(r"[-_]", slug)
    words = [w for w in words if w not in STOPWORDS_IN_FILENAME]

    filename = "_".join(words) if words else slug

    return f"{filename}.txt"


# ============================================================
# ENTRYPOINT
# ============================================================

asyncio.run(crawl_batch())
