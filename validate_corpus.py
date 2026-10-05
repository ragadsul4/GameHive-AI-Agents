import json
from collections import Counter


# =========================================================
# Configuration
# =========================================================

INPUT_FILE = "data/ingested/official_sources.jsonl"

MIN_WORDS = 100


NOISE_PATTERNS = [
    "web browser not supported",
    "periodic reporting questionnaire",
    "state of conservation",
    "international assistance",
    "world heritage fund",
    "minor boundary modifications",
    "decision |",
    "properties inscribed on the world heritage list",
    "arab states, world heritage",
]


# =========================================================
# Load Corpus
# =========================================================

def load_sources():

    records = []

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        for line in file:

            line = line.strip()

            if not line:
                continue

            records.append(
                json.loads(line)
            )

    return records


# =========================================================
# Audit One Source
# =========================================================

def audit_source(source):

    text = source.get(
        "text",
        ""
    )

    lowered = text.lower()

    noise_found = [
        pattern
        for pattern in NOISE_PATTERNS
        if pattern in lowered
    ]

    word_count = len(
        text.split()
    )

    status = "PASS"

    reasons = []

    # ---------------------------------------------
    # Evidence-role check
    # ---------------------------------------------

    source_role = source.get(
        "source_role",
        "unknown"
    )

    if source_role != "evidence":

        status = "WARN"

        reasons.append(
            f"source_role={source_role}"
        )

    # ---------------------------------------------
    # Minimum content size
    # ---------------------------------------------

    if word_count < MIN_WORDS:

        status = "WARN"

        reasons.append(
            f"only {word_count} words"
        )

    # ---------------------------------------------
    # Noise detection
    # ---------------------------------------------

    if noise_found:

        status = "WARN"

        reasons.append(
            f"{len(noise_found)} noise pattern(s)"
        )

    return {

        "name":
            source.get(
                "source_name",
                "Unknown"
            ),

        "organization":
            source.get(
                "organization",
                "Unknown"
            ),

        "category":
            source.get(
                "category",
                "unknown"
            ),

        "role":
            source_role,

        "trust_tier":
            source.get(
                "trust_tier",
                "unknown"
            ),

        "characters":
            len(text),

        "words":
            word_count,

        "noise":
            noise_found,

        "status":
            status,

        "reasons":
            reasons
    }


# =========================================================
# Main
# =========================================================

def main():

    sources = load_sources()

    results = []

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE CULTURAL CORPUS AUDIT"
    )

    print(
        "================================="
    )

    for source in sources:

        result = audit_source(
            source
        )

        results.append(
            result
        )

        print(
            "\n---------------------------------"
        )

        print(
            f"Source: {result['name']}"
        )

        print(
            f"Organization: "
            f"{result['organization']}"
        )

        print(
            f"Category: "
            f"{result['category']}"
        )

        print(
            f"Role: "
            f"{result['role']}"
        )

        print(
            f"Trust Tier: "
            f"{result['trust_tier']}"
        )

        print(
            f"Characters: "
            f"{result['characters']}"
        )

        print(
            f"Words: "
            f"{result['words']}"
        )

        print(
            f"Status: "
            f"{result['status']}"
        )

        if result["reasons"]:

            print(
                "Reasons:"
            )

            for reason in result[
                "reasons"
            ]:

                print(
                    f"  - {reason}"
                )

        if result["noise"]:

            print(
                "Noise detected:"
            )

            for noise in result[
                "noise"
            ]:

                print(
                    f"  - {noise}"
                )

    # =====================================================
    # Summary
    # =====================================================

    statuses = Counter(
        item["status"]
        for item in results
    )

    print(
        "\n================================="
    )

    print(
        "CORPUS AUDIT SUMMARY"
    )

    print(
        "================================="
    )

    print(
        f"Sources checked: "
        f"{len(results)}"
    )

    print(
        f"PASS: "
        f"{statuses['PASS']}"
    )

    print(
        f"WARN: "
        f"{statuses['WARN']}"
    )

    print(
        "\nAudit complete."
    )


if __name__ == "__main__":
    main()