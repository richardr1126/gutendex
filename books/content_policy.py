"""Catalog exclusions, not a per-book age rating or a full-text classifier.

Gutenberg's English subject headings apply across languages. Excluding the
whole Sexuality & Erotica shelf is deliberately conservative: it also removes
some educational books rather than relying on incomplete genre subjects.
ID exclusions survive missing or changed metadata and cover known explicit
works. Keep reasons beside IDs so additions can be reviewed and reversed.
"""
from django.db.models import Q

POLICY_VERSION = "1"

EXCLUDED_IDS = {
    20028: "Fanny Hill audiobook; explicit erotic work",
    25305: "Memoirs of Fanny Hill; explicit erotic work",
    30254: "The Romance of Lust; explicit erotic work",
}


def filter_catalog(queryset):
    blocked = Q(gutenberg_id__in=EXCLUDED_IDS)
    for term in ("erotic", "pornograph", "sadism", "sadistic"):
        blocked |= Q(subjects__name__icontains=term)
        blocked |= Q(bookshelves__name__icontains=term)
    blocked |= Q(bookshelves__name__icontains="Sexuality & Erotica")
    # Titles provide a second signal for records with incomplete subjects.
    # Plain romance, sex education, war and horror are not blanket exclusions.
    blocked |= Q(title__icontains="erotic") | Q(title__icontains="pornograph")
    return queryset.exclude(blocked)
