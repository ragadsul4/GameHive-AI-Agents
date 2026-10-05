import json
import hashlib
import os
import re
from datetime import datetime, timezone

import requests
import trafilatura
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from RAG.source_registry import TRUSTED_SOURCES


# =========================================================
# Configuration
# =========================================================

OUTPUT_FOLDER = "data/ingested"

OUTPUT_FILE = os.path.join(
    OUTPUT_FOLDER,
    "official_sources.jsonl"
)

MIN_CONTENT_LENGTH = 500
MIN_WORD_COUNT = 80


HEADERS = {
    "User-Agent": (
        "GameHive-CulturalResearch/1.0 "
        "(Educational cultural research project)"
    ),
    "Accept-Language": "ar,en;q=0.9",
}


# =========================================================
# Known Website Noise
# =========================================================

# These phrases usually mean the entire extracted line
# is navigation / administrative website noise.
BLOCKED_PHRASES = [
    "Web Browser not supported",
    "Periodic Reporting Questionnaire",
    "Arab States, World Heritage",
    "World Heritage Regional page",
    "World Heritage Fund",
    "International Assistance",
    "Forgot your username",
    "Become a member",
    "Follow us",
    "Privacy Notice",
    "Terms of use",
    "Cookie policy",
    "Accept cookies",
    "Subscribe to our newsletter",
    "Login",
    "Sign in",
    "Skip to main content",
]


# These phrases may appear INSIDE a useful line.
# We remove only the phrase itself and keep the
# cultural evidence surrounding it.
INLINE_NOISE_PHRASES = [
    "Your browser is not supported by this application.",
    (
        "Please use recent versions of browsers such as "
        "Google Chrome, Firefox, Edge or Safari to access "
        "'Dive' interfaces."
    ),
    "Latest news and events",
    "On the implementation of the Convention",
    "Ratification of the Convention on",
    "Read the Convention in:",
]


# =========================================================
# HTTP Session
# =========================================================

def create_session():
    """
    Create a reliable HTTP session with automatic retries.
    """

    session = requests.Session()

    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504
        ],
        allowed_methods=["GET"]
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy
    )

    session.mount(
        "http://",
        adapter
    )

    session.mount(
        "https://",
        adapter
    )

    session.headers.update(
        HEADERS
    )

    return session


SESSION = create_session()


# =========================================================
# Noise Removal
# =========================================================

def is_noise_line(line: str) -> bool:
    """
    Detect whether an extracted line is mainly
    navigation / administrative website noise.
    """

    line_lower = line.lower()

    for phrase in BLOCKED_PHRASES:

        if phrase.lower() in line_lower:
            return True

    return False


def remove_inline_noise(line: str) -> str:
    """
    Remove known inline boilerplate while keeping
    the useful evidence on the same line.
    """

    cleaned = line

    for phrase in INLINE_NOISE_PHRASES:

        cleaned = re.sub(
            re.escape(phrase),
            " ",
            cleaned,
            flags=re.IGNORECASE
        )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned
    )

    return cleaned.strip()


def normalize_text(text: str) -> str:
    """
    Clean extracted content.

    Removes:
    - Empty lines
    - Very short fragments
    - Duplicate lines
    - Website navigation
    - Browser warnings
    - Repeated whitespace

    Useful cultural information is preserved.
    """

    if not text:
        return ""

    cleaned_lines = []
    seen_lines = set()

    for raw_line in text.splitlines():

        line = raw_line.strip()

        # Normalize whitespace
        line = re.sub(
            r"\s+",
            " ",
            line
        )

        # Remove inline boilerplate
        # without removing the entire useful line.
        line = remove_inline_noise(
            line
        )

        if len(line) < 4:
            continue

        # Remove full noisy lines
        if is_noise_line(line):
            continue

        normalized_key = line.lower()

        # Avoid duplicate extracted lines
        if normalized_key in seen_lines:
            continue

        seen_lines.add(
            normalized_key
        )

        cleaned_lines.append(
            line
        )

    return "\n".join(
        cleaned_lines
    )


# =========================================================
# BeautifulSoup Fallback
# =========================================================

def clean_fallback(html: str) -> str:
    """
    Backup extraction strategy.

    Used when Trafilatura cannot retrieve enough
    useful content from the webpage.
    """

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Remove structural website noise
    for tag in soup([
        "script",
        "style",
        "nav",
        "footer",
        "header",
        "form",
        "noscript",
        "svg",
        "iframe",
        "aside"
    ]):
        tag.decompose()

    # Remove common navigation containers
    for selector in [
        "[role='navigation']",
        ".navigation",
        ".navbar",
        ".menu",
        ".footer",
        ".header",
        ".sidebar",
        ".breadcrumbs",
        ".breadcrumb"
    ]:

        for element in soup.select(
            selector
        ):
            element.decompose()

    text = soup.get_text(
        separator="\n",
        strip=True
    )

    return normalize_text(
        text
    )


# =========================================================
# Main Extraction
# =========================================================

def extract_text(html: str) -> str:
    """
    Precision-first webpage extraction.

    Strategy:
    1. Use Trafilatura first.
    2. Clean the extracted text.
    3. If content is too small,
       use BeautifulSoup as fallback.

    We do not automatically choose the longest output,
    because longer extraction may simply contain
    more website noise.
    """

    primary_text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        include_links=False,
        include_images=False,
        favor_precision=True
    )

    primary_text = normalize_text(
        primary_text or ""
    )

    if len(primary_text) >= MIN_CONTENT_LENGTH:
        return primary_text

    fallback_text = clean_fallback(
        html
    )

    if len(fallback_text) > len(primary_text):
        return fallback_text

    return primary_text


# =========================================================
# Content Quality Gate
# =========================================================

def validate_content(text: str):
    """
    Validate source content before allowing it
    into the cultural evidence corpus.

    Returns:
        (valid: bool, reason: str)
    """

    if not text:

        return (
            False,
            "empty content"
        )

    content_length = len(
        text
    )

    if content_length < MIN_CONTENT_LENGTH:

        return (
            False,
            f"only {content_length} characters"
        )

    word_count = len(
        text.split()
    )

    if word_count < MIN_WORD_COUNT:

        return (
            False,
            f"only {word_count} words"
        )

    # Check for remaining major website noise
    noise_hits = 0

    for phrase in BLOCKED_PHRASES:

        if phrase.lower() in text.lower():
            noise_hits += 1

    if noise_hits >= 4:

        return (
            False,
            f"too much website boilerplate "
            f"({noise_hits} noise indicators)"
        )

    return (
        True,
        "content passed quality checks"
    )


# =========================================================
# Hashing
# =========================================================

def generate_hash(text: str) -> str:
    """
    Generate a SHA-256 content fingerprint.

    Used later to detect whether a source changes.
    """

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


# =========================================================
# Source Fetching
# =========================================================

def fetch_source(source: dict):

    print(
        f"\nFetching: {source['name']}"
    )

    print(
        f"URL: {source['url']}"
    )

    try:

        response = SESSION.get(
            source["url"],
            timeout=30
        )

        response.raise_for_status()

        # Helps with Arabic websites
        if response.apparent_encoding:

            response.encoding = (
                response.apparent_encoding
            )

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        # Current pipeline handles HTML pages
        if (
            "text/html" not in content_type
            and
            "application/xhtml" not in content_type
        ):

            print(
                "SKIPPED: unsupported content type "
                f"({content_type})"
            )

            return None

        # =================================================
        # Extract
        # =================================================

        text = extract_text(
            response.text
        )

        # =================================================
        # Quality Gate
        # =================================================

        is_valid, reason = validate_content(
            text
        )

        if not is_valid:

            print(
                f"SKIPPED: {reason}"
            )

            return None

        content_length = len(
            text
        )

        word_count = len(
            text.split()
        )

        # =================================================
        # Structured Evidence Record
        # =================================================

        record = {

            "source_id":
                source["id"],

            "source_name":
                source["name"],

            "organization":
                source["organization"],

            "source_url":
                source["url"],

            "category":
                source["category"],

            # Evidence / catalog / reference governance
            "source_role":
                source.get(
                    "source_role",
                    "evidence"
                ),

            "trust_tier":
                source["trust_tier"],

            "language":
                source["language"],

            "retrieved_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "content_hash":
                generate_hash(
                    text
                ),

            "content_length":
                content_length,

            "word_count":
                word_count,

            "text":
                text
        }

        print(
            f"SUCCESS: "
            f"{content_length} characters | "
            f"{word_count} words | "
            f"role={record['source_role']}"
        )

        return record

    except requests.exceptions.Timeout:

        print(
            "FAILED: request timed out"
        )

        return None

    except requests.exceptions.HTTPError as error:

        print(
            f"FAILED: HTTP error - {error}"
        )

        return None

    except requests.exceptions.RequestException as error:

        print(
            f"FAILED: connection error - {error}"
        )

        return None

    except Exception as error:

        print(
            f"FAILED: unexpected error - {error}"
        )

        return None


# =========================================================
# Main Pipeline
# =========================================================

def main():

    os.makedirs(
        OUTPUT_FOLDER,
        exist_ok=True
    )

    records = []

    successful_sources = 0

    failed_sources = 0

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE CULTURAL SOURCE INGESTION"
    )

    print(
        "================================="
    )

    # =====================================================
    # Process Trusted Evidence Sources
    # =====================================================

    for source in TRUSTED_SOURCES:

        record = fetch_source(
            source
        )

        if record:

            records.append(
                record
            )

            successful_sources += 1

        else:

            failed_sources += 1

    # =====================================================
    # Save Accepted Evidence Sources
    # =====================================================

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        for record in records:

            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False
                )
                + "\n"
            )

    # =====================================================
    # Summary
    # =====================================================

    print(
        "\n================================="
    )

    print(
        "INGESTION SUMMARY"
    )

    print(
        "================================="
    )

    print(
        f"Accepted sources: "
        f"{successful_sources}"
    )

    print(
        f"Rejected/failed sources: "
        f"{failed_sources}"
    )

    print(
        f"Total trusted sources checked: "
        f"{len(TRUSTED_SOURCES)}"
    )

    print(
        f"\nSaved to: {OUTPUT_FILE}"
    )


# =========================================================
# Entry Point
# =========================================================

if __name__ == "__main__":

    main()