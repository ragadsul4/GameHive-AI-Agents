# =========================================================
# GameHive Cultural Evidence Source Registry
# =========================================================
#
# IMPORTANT:
# TRUSTED_SOURCES contains EVIDENCE sources only.
#
# General index pages, administrative documents,
# decisions, maps, and periodic reports should NOT
# enter the main cultural verification corpus.
# =========================================================


TRUSTED_SOURCES = [

    # =====================================================
    # UNESCO WORLD HERITAGE
    # Saudi Arabia — Detailed Evidence Pages
    # =====================================================

    {
        "id": "unesco_hegra",
        "name": "Hegra Archaeological Site",
        "organization": "UNESCO World Heritage Centre",
        "url": "https://whc.unesco.org/en/list/1293",
        "category": "archaeology",
        "source_role": "evidence",
        "trust_tier": 1,
        "language": "en"
    },

    {
        "id": "unesco_at_turaif",
        "name": "At-Turaif District in ad-Dir'iyah",
        "organization": "UNESCO World Heritage Centre",
        "url": "https://whc.unesco.org/en/list/1329",
        "category": "architecture_history",
        "source_role": "evidence",
        "trust_tier": 1,
        "language": "en"
    },

    {
        "id": "unesco_historic_jeddah",
        "name": "Historic Jeddah, the Gate to Makkah",
        "organization": "UNESCO World Heritage Centre",
        "url": "https://whc.unesco.org/en/list/1361",
        "category": "red_sea_heritage",
        "source_role": "evidence",
        "trust_tier": 1,
        "language": "en"
    },

    {
        "id": "unesco_hail_rock_art",
        "name": "Rock Art in the Hail Region of Saudi Arabia",
        "organization": "UNESCO World Heritage Centre",
        "url": "https://whc.unesco.org/en/list/1472",
        "category": "rock_art",
        "source_role": "evidence",
        "trust_tier": 1,
        "language": "en"
    },

    {
        "id": "unesco_al_ahsa",
        "name": "Al-Ahsa Oasis, an Evolving Cultural Landscape",
        "organization": "UNESCO World Heritage Centre",
        "url": "https://whc.unesco.org/en/list/1563",
        "category": "oasis_cultural_landscape",
        "source_role": "evidence",
        "trust_tier": 1,
        "language": "en"
    },

    {
        "id": "unesco_hima",
        "name": "Hima Cultural Area",
        "organization": "UNESCO World Heritage Centre",
        "url": "https://whc.unesco.org/en/list/1619",
        "category": "rock_art_caravan_history",
        "source_role": "evidence",
        "trust_tier": 1,
        "language": "en"
    },

    {
        "id": "unesco_uruq_bani_maarid",
        "name": "Uruq Bani Ma'arid",
        "organization": "UNESCO World Heritage Centre",
        "url": "https://whc.unesco.org/en/list/1699",
        "category": "natural_heritage",
        "source_role": "evidence",
        "trust_tier": 1,
        "language": "en"
    },

    {
        "id": "unesco_al_faw",
        "name": "The Cultural Landscape of Al-Faw Archaeological Area",
        "organization": "UNESCO World Heritage Centre",
        "url": "https://whc.unesco.org/en/list/1712",
        "category": "archaeology_cultural_landscape",
        "source_role": "evidence",
        "trust_tier": 1,
        "language": "en"
    },


    # =====================================================
    # UNESCO INTANGIBLE CULTURAL HERITAGE
    # =====================================================

    {
        "id": "unesco_saudi_intangible_heritage",
        "name": "Saudi Arabia - Intangible Cultural Heritage",
        "organization": "UNESCO",
        "url": "https://ich.unesco.org/en-state/saudi-arabia-SA",
        "category": "intangible_heritage",
        "source_role": "evidence",
        "trust_tier": 1,
        "language": "en"
    },


    # =====================================================
    # OFFICIAL SAUDI SOURCES
    # Keep as additional authoritative evidence sources.
    # =====================================================

    {
        "id": "saudi_tangible_heritage",
        "name": "Saudi Tangible Cultural Heritage",
        "organization": (
            "Saudi National Commission for "
            "Education, Culture and Science"
        ),
        "url": (
            "https://snc-ecs.moc.gov.sa/"
            "tangible-heritage/?lang=ar"
        ),
        "category": "tangible_heritage",
        "source_role": "evidence",
        "trust_tier": 1,
        "language": "ar"
    },

    {
        "id": "saudi_intangible_heritage",
        "name": "Saudi Intangible Cultural Heritage",
        "organization": (
            "Saudi National Commission for "
            "Education, Culture and Science"
        ),
        "url": (
            "https://snc-ecs.moc.gov.sa/"
            "intangible-heritage/?lang=ar"
        ),
        "category": "intangible_heritage",
        "source_role": "evidence",
        "trust_tier": 1,
        "language": "ar"
    }
]


# =========================================================
# Discovery / Catalog Sources
# =========================================================
#
# These sources are useful for finding material,
# but should NOT be indexed as cultural evidence.
# =========================================================

DISCOVERY_SOURCES = [

    {
        "id": "unesco_saudi_world_heritage_catalog",
        "name": "UNESCO - Saudi Arabia World Heritage Overview",
        "organization": "UNESCO World Heritage Centre",
        "url": "https://whc.unesco.org/en/statesparties/sa",
        "source_role": "catalog"
    }

]