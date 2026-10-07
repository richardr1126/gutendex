"""Catalog exclusions, not a per-book age rating or a full-text classifier.

Gutenberg's English subject headings apply across languages. Excluding the
whole Sexuality & Erotica shelf is deliberately conservative: it also removes
some educational books rather than relying on incomplete genre subjects.
ID exclusions survive missing or changed metadata and cover known explicit
works. Keep reasons beside IDs so additions can be reviewed and reversed.
"""
from django.db.models import Q

from .models import Book

POLICY_VERSION = "1"

EXCLUDED_IDS = {
    20028: "Fanny Hill audiobook; explicit erotic work",
    25305: "Memoirs of Fanny Hill; explicit erotic work",
    30254: "The Romance of Lust; explicit erotic work",
}


def filter_catalog(queryset):
    # Resolve matching metadata to book IDs once. Related-field exclusions
    # otherwise become nine correlated EXISTS checks per candidate book,
    # repeated for the exact pagination count across the complete catalog.
    subject_terms = Q()
    shelf_terms = Q()
    for term in ("erotic", "pornograph", "sadism", "sadistic"):
        subject_terms |= Q(subject__name__icontains=term)
        shelf_terms |= Q(bookshelf__name__icontains=term)
    shelf_terms |= Q(bookshelf__name__icontains="Sexuality & Erotica")
    subject_ids = Book.subjects.through.objects.filter(subject_terms).values("book_id")
    shelf_ids = Book.bookshelves.through.objects.filter(shelf_terms).values("book_id")
    blocked = (Q(gutenberg_id__in=EXCLUDED_IDS) | Q(pk__in=subject_ids)
               | Q(pk__in=shelf_ids))
    # Titles provide a second signal for records with incomplete subjects.
    # Plain romance, sex education, war and horror are not blanket exclusions.
    blocked |= Q(title__icontains="erotic") | Q(title__icontains="pornograph")
    return queryset.exclude(blocked)
