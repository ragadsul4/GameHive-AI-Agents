import json
import hashlib
import os
import re

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


# =========================================================
# Configuration
# =========================================================

INPUT_FILE = "data/ingested/official_sources.jsonl"

DB_FOLDER = "chroma_db"

COLLECTION_NAME = "culture_sources"


MAX_CHUNK_SIZE = 1200

# Approximate maximum overlap size.
# Overlap is now made from COMPLETE sentences.
CHUNK_OVERLAP = 200

MIN_CHUNK_SIZE = 120


# =========================================================
# Administrative / Website Noise
# =========================================================

NOISE_PATTERNS = [
    "state of conservation",
    "periodic reporting questionnaire",
    "web browser not supported",
    "international assistance",
    "world heritage fund",
    "minor boundary modifications",
    "properties inscribed on the world heritage list",
    "arab states, world heritage",
    "world heritage regional page",
]


# =========================================================
# Embedding Model
# =========================================================

embedding_function = DefaultEmbeddingFunction()


# =========================================================
# General Helpers
# =========================================================

def generate_hash(text: str) -> str:
    """
    Generate a SHA-256 fingerprint for text.

    Used for:
    - Deduplication
    - Auditability
    - Change tracking
    """

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


# =========================================================
# Paragraph Cleaning
# =========================================================

def clean_paragraphs(text: str) -> list[str]:
    """
    Split source text into meaningful paragraphs.

    Removes:
    - Empty lines
    - Extremely short fragments
    - Excessive whitespace
    """

    paragraphs = []

    for paragraph in text.split("\n"):

        paragraph = paragraph.strip()

        paragraph = re.sub(
            r"\s+",
            " ",
            paragraph
        )

        if len(paragraph) >= 20:

            paragraphs.append(
                paragraph
            )

    return paragraphs


# =========================================================
# Sentence Splitting
# =========================================================

def split_into_sentences(text: str) -> list[str]:
    """
    Split text into complete sentences.

    Supports common:
    - English sentence endings
    - Arabic question marks

    This prevents normal chunks from starting
    in the middle of a sentence.
    """

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?؟])\s+",
        text
    )

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


# =========================================================
# Noise Cleaning
# =========================================================

def clean_chunk_noise(text: str):
    """
    Remove known administrative / website noise.

    Important:
    We remove the noisy PHRASE instead of deleting
    an entire useful cultural chunk.

    Returns:
        cleaned_text
        noise_found
    """

    if not text:
        return "", []

    cleaned_text = text

    noise_found = []

    for pattern in NOISE_PATTERNS:

        if pattern.lower() in cleaned_text.lower():

            noise_found.append(
                pattern
            )

            cleaned_text = re.sub(
                re.escape(pattern),
                " ",
                cleaned_text,
                flags=re.IGNORECASE
            )

    # Normalize whitespace after cleaning
    cleaned_text = re.sub(
        r"[ \t]+",
        " ",
        cleaned_text
    )

    cleaned_text = re.sub(
        r"\n\s*\n+",
        "\n",
        cleaned_text
    )

    cleaned_text = cleaned_text.strip()

    return (
        cleaned_text,
        noise_found
    )


# =========================================================
# Sentence-Aware Smart Chunking
# =========================================================

def smart_chunk_text(text: str) -> list[str]:
    """
    Professional sentence-aware chunking.

    Goals:
    - Preserve complete sentences
    - Avoid arbitrary character cuts
    - Preserve paragraph meaning
    - Keep contextual overlap
    - Make overlap from COMPLETE sentences

    Normal chunks should therefore not begin
    halfway through a sentence.
    """

    paragraphs = clean_paragraphs(
        text
    )

    chunks = []

    current_sentences = []

    # =====================================================
    # Process Paragraphs
    # =====================================================

    for paragraph in paragraphs:

        sentences = split_into_sentences(
            paragraph
        )

        for sentence in sentences:

            # -------------------------------------------------
            # Very long single sentence
            # -------------------------------------------------
            #
            # MAX_CHUNK_SIZE is our preferred size,
            # not a reason to destroy sentence integrity.
            #
            # If one genuine sentence is slightly larger,
            # keep it whole rather than cutting raw characters.
            # -------------------------------------------------

            if (
                len(sentence) > MAX_CHUNK_SIZE
                and not current_sentences
            ):

                chunks.append(
                    sentence
                )

                continue

            # -------------------------------------------------
            # Try adding sentence to current chunk
            # -------------------------------------------------

            candidate_sentences = (
                current_sentences
                + [sentence]
            )

            candidate = " ".join(
                candidate_sentences
            ).strip()

            # -------------------------------------------------
            # Sentence still fits
            # -------------------------------------------------

            if len(candidate) <= MAX_CHUNK_SIZE:

                current_sentences.append(
                    sentence
                )

                continue

            # -------------------------------------------------
            # Current chunk is full
            # -------------------------------------------------

            if current_sentences:

                completed_chunk = " ".join(
                    current_sentences
                ).strip()

                if (
                    len(completed_chunk)
                    >= MIN_CHUNK_SIZE
                ):

                    chunks.append(
                        completed_chunk
                    )

            # -------------------------------------------------
            # Build sentence-level overlap
            # -------------------------------------------------
            #
            # Old implementation:
            #
            # current_chunk[-200:]
            #
            # That could start in the middle of a word
            # or sentence.
            #
            # New implementation:
            #
            # Use COMPLETE previous sentences only.
            # -------------------------------------------------

            overlap_sentences = []

            overlap_size = 0

            for previous_sentence in reversed(
                current_sentences
            ):

                proposed_size = (
                    overlap_size
                    + len(previous_sentence)
                    + 1
                )

                if proposed_size > CHUNK_OVERLAP:
                    break

                overlap_sentences.insert(
                    0,
                    previous_sentence
                )

                overlap_size = proposed_size

            # -------------------------------------------------
            # New chunk begins with complete sentences
            # -------------------------------------------------

            current_sentences = (
                overlap_sentences
                + [sentence]
            )

            # -------------------------------------------------
            # If the new sentence itself is unusually large
            # -------------------------------------------------

            new_chunk = " ".join(
                current_sentences
            ).strip()

            if len(new_chunk) > MAX_CHUNK_SIZE:

                # Save overlap separately if useful
                if overlap_sentences:

                    overlap_text = " ".join(
                        overlap_sentences
                    ).strip()

                    if (
                        len(overlap_text)
                        >= MIN_CHUNK_SIZE
                    ):

                        chunks.append(
                            overlap_text
                        )

                # Preserve the long sentence whole
                chunks.append(
                    sentence
                )

                current_sentences = []

    # =====================================================
    # Save Final Remaining Chunk
    # =====================================================

    if current_sentences:

        final_chunk = " ".join(
            current_sentences
        ).strip()

        if len(final_chunk) >= MIN_CHUNK_SIZE:

            chunks.append(
                final_chunk
            )

    return chunks


# =========================================================
# Load Sources
# =========================================================

def load_sources():
    """
    Load the trusted, already-ingested cultural sources.
    """

    if not os.path.exists(
        INPUT_FILE
    ):

        raise FileNotFoundError(
            f"Cannot find: {INPUT_FILE}"
        )

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

            record = json.loads(
                line
            )

            records.append(
                record
            )

    return records


# =========================================================
# Build Index
# =========================================================

def build_index():

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE CULTURAL RAG INDEX"
    )

    print(
        "================================="
    )

    sources = load_sources()

    print(
        f"\nLoaded sources: "
        f"{len(sources)}"
    )

    # =====================================================
    # ChromaDB
    # =====================================================

    client = chromadb.PersistentClient(
        path=DB_FOLDER
    )

    # -----------------------------------------------------
    # Remove Previous Collection
    # -----------------------------------------------------

    try:

        client.delete_collection(
            name=COLLECTION_NAME
        )

        print(
            "Old collection removed."
        )

    except Exception:

        pass

    # -----------------------------------------------------
    # Create Fresh Collection
    # -----------------------------------------------------

    collection = client.create_collection(

        name=COLLECTION_NAME,

        embedding_function=embedding_function,

        metadata={
            "description":
                (
                    "GameHive verified cultural "
                    "evidence corpus"
                )
        }
    )

    # =====================================================
    # Storage Containers
    # =====================================================

    documents = []

    metadatas = []

    ids = []

    seen_chunk_hashes = set()

    # =====================================================
    # Counters
    # =====================================================

    total_duplicates = 0

    total_noise_cleaned = 0

    total_rejected_chunks = 0

    total_non_evidence_sources = 0


    # =====================================================
    # Process Sources
    # =====================================================

    for source in sources:

        # -------------------------------------------------
        # Source Governance Gate
        # -------------------------------------------------

        source_role = source.get(
            "source_role",
            "evidence"
        )

        if source_role != "evidence":

            total_non_evidence_sources += 1

            print(
                f"\nSKIPPED SOURCE: "
                f"{source['source_name']}"
            )

            print(
                f"  Reason: source_role="
                f"{source_role}"
            )

            continue

        source_id = source[
            "source_id"
        ]

        source_name = source[
            "source_name"
        ]

        text = source[
            "text"
        ]

        # =================================================
        # Sentence-Aware Chunking
        # =================================================

        chunks = smart_chunk_text(
            text
        )

        print(
            f"\n{source_name}"
        )

        print(
            f"  Generated chunks: "
            f"{len(chunks)}"
        )

        accepted_chunks = 0

        source_cleaned_chunks = 0

        source_rejected_chunks = 0

        # =================================================
        # Process Every Chunk
        # =================================================

        for index, original_chunk in enumerate(
            chunks
        ):

            # ---------------------------------------------
            # Evidence Noise Cleaning
            # ---------------------------------------------

            cleaned_chunk, noise_found = (
                clean_chunk_noise(
                    original_chunk
                )
            )

            if noise_found:

                total_noise_cleaned += 1

                source_cleaned_chunks += 1

            # ---------------------------------------------
            # Quality Gate After Cleaning
            # ---------------------------------------------

            if len(cleaned_chunk) < MIN_CHUNK_SIZE:

                total_rejected_chunks += 1

                source_rejected_chunks += 1

                continue

            # ---------------------------------------------
            # Hash AFTER Cleaning
            # ---------------------------------------------

            chunk_hash = generate_hash(
                cleaned_chunk
            )

            # ---------------------------------------------
            # Deduplication
            # ---------------------------------------------

            if chunk_hash in seen_chunk_hashes:

                total_duplicates += 1

                continue

            seen_chunk_hashes.add(
                chunk_hash
            )

            # ---------------------------------------------
            # Stable Chunk ID
            # ---------------------------------------------

            chunk_id = (
                f"{source_id}_"
                f"{index}_"
                f"{chunk_hash[:10]}"
            )

            # ---------------------------------------------
            # Store Evidence
            # ---------------------------------------------

            documents.append(
                cleaned_chunk
            )

            # ---------------------------------------------
            # Rich Evidence Metadata
            # ---------------------------------------------

            metadatas.append(
                {

                    "source_id":
                        source_id,

                    "source_name":
                        source_name,

                    "organization":
                        source[
                            "organization"
                        ],

                    "source_url":
                        source[
                            "source_url"
                        ],

                    "category":
                        source[
                            "category"
                        ],

                    "source_role":
                        source_role,

                    "trust_tier":
                        int(
                            source[
                                "trust_tier"
                            ]
                        ),

                    "language":
                        source[
                            "language"
                        ],

                    "retrieved_at":
                        source[
                            "retrieved_at"
                        ],

                    "source_content_hash":
                        source[
                            "content_hash"
                        ],

                    "chunk_hash":
                        chunk_hash,

                    "chunk_index":
                        index,

                    "chunk_count":
                        len(chunks),

                    # Indicates whether boilerplate/noise
                    # was removed from this evidence chunk.
                    "noise_cleaned":
                        bool(
                            noise_found
                        ),

                    # Makes the chunking strategy visible
                    # later for audits/debugging.
                    "chunking_strategy":
                        "sentence_aware"
                }
            )

            ids.append(
                chunk_id
            )

            accepted_chunks += 1

        # =================================================
        # Per-Source Summary
        # =================================================

        print(
            f"  Indexed chunks: "
            f"{accepted_chunks}"
        )

        print(
            f"  Cleaned chunks: "
            f"{source_cleaned_chunks}"
        )

        print(
            f"  Rejected chunks: "
            f"{source_rejected_chunks}"
        )

    # =====================================================
    # Safety Check
    # =====================================================

    if not documents:

        raise RuntimeError(
            "No valid evidence chunks were created."
        )

    # =====================================================
    # Store in ChromaDB
    # =====================================================

    collection.add(

        documents=documents,

        metadatas=metadatas,

        ids=ids
    )

    # =====================================================
    # Final Summary
    # =====================================================

    print(
        "\n================================="
    )

    print(
        "INDEX BUILD SUMMARY"
    )

    print(
        "================================="
    )

    print(
        f"Loaded sources: "
        f"{len(sources)}"
    )

    print(
        f"Non-evidence sources skipped: "
        f"{total_non_evidence_sources}"
    )

    print(
        f"Unique indexed chunks: "
        f"{len(documents)}"
    )

    print(
        f"Chunks cleaned for noise: "
        f"{total_noise_cleaned}"
    )

    print(
        f"Chunks rejected after cleaning: "
        f"{total_rejected_chunks}"
    )

    print(
        f"Duplicate chunks removed: "
        f"{total_duplicates}"
    )

    print(
        f"Chroma collection count: "
        f"{collection.count()}"
    )

    print(
        "Chunking strategy: "
        "sentence-aware"
    )

    print(
        "\nCultural evidence index is ready."
    )


# =========================================================
# Entry Point
# =========================================================

if __name__ == "__main__":

    build_index()
