from django.db.models import Q
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Book, Bookshelf, Format, Language, Person, Subject


class CatalogQueryTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def book(self, identifier, title="A book", authors=(), languages=(),
             formats=(), subjects=(), shelves=(), popularity=1):
        book = Book.objects.create(
            gutenberg_id=identifier, title=title, media_type="Text",
            copyright=False, download_count=popularity,
        )
        for author in authors:
            values = {"name": author} if isinstance(author, str) else author
            book.authors.add(Person.objects.create(**values))
        for language in languages:
            book.languages.add(Language.objects.get_or_create(code=language)[0])
        for index, mime_type in enumerate(formats):
            Format.objects.create(book=book, mime_type=mime_type,
                                  url="https://example.com/%d/%d" % (identifier, index))
        for subject in subjects:
            book.subjects.add(Subject.objects.get_or_create(name=subject)[0])
        for shelf in shelves:
            book.bookshelves.add(Bookshelf.objects.get_or_create(name=shelf)[0])
        return book

    def results(self, parameters):
        response = self.client.get("/books/", parameters)
        self.assertEqual(response.status_code, 200)
        return response.data

    def result_ids(self, parameters):
        data = self.results(parameters)
        self.assertIsNone(data["next"], "Use explicit pages for larger result sets")
        return [book["id"] for book in data["results"]]

    def legacy_search_ids(self, search):
        # Separate filter calls deliberately allow different related authors to
        # satisfy different words, just as the public endpoint historically did.
        queryset = Book.objects.all()
        for term in search.replace("\x00", "").split(" ")[:4]:
            queryset = queryset.filter(Q(authors__name__icontains=term) |
                                       Q(title__icontains=term))
        return list(queryset.order_by("gutenberg_id").values_list(
            "gutenberg_id", flat=True).distinct())

    def test_search_terms_can_match_distinct_authors(self):
        self.book(101, authors=("Alice Writer", "Bob Writer"))
        self.book(102, authors=("Alice Writer",))
        self.book(103, authors=("Bob Writer",))
        self.book(104, authors=("Someone Else",))
        parameters = {"search": "alice bob"}
        self.assertEqual(self.result_ids(parameters), [101])
        self.assertEqual(self.result_ids(parameters), self.legacy_search_ids("alice bob"))

    def test_search_can_mix_title_and_author_terms(self):
        self.book(201, title="Voyage across the sea", authors=("Alice Writer",))
        self.book(202, title="Voyage across the sea", authors=("Other Writer",))
        self.book(203, title="A different story", authors=("Alice Writer",))
        self.assertEqual(self.result_ids({"search": "voyage alice"}), [201])
        self.assertEqual(self.result_ids({"search": "voyage alice"}),
                         self.legacy_search_ids("voyage alice"))

    def test_title_search_retains_books_without_authors(self):
        self.book(301, title="The silent voyage")
        self.book(302, title="A different story")
        self.assertEqual(self.result_ids({"search": "silent voyage"}), [301])
        self.assertEqual(self.result_ids({"search": "silent voyage"}),
                         self.legacy_search_ids("silent voyage"))

    def test_author_year_bounds_can_match_distinct_authors(self):
        self.book(401, authors=({"name": "Early", "birth_year": 1700, "death_year": 1750},
                               {"name": "Late", "birth_year": 1950, "death_year": 2000}))
        self.book(402, authors=({"name": "Early only", "birth_year": 1700},))
        self.book(403, authors=({"name": "Late only", "death_year": 2000},))
        self.book(404)
        legacy = Book.objects.filter(
            Q(authors__birth_year__lte=1800) | Q(authors__death_year__lte=1800)
        ).filter(
            Q(authors__birth_year__gte=1900) | Q(authors__death_year__gte=1900)
        ).values_list("gutenberg_id", flat=True).distinct()
        actual = self.result_ids({"author_year_end": "1800", "author_year_start": "1900"})
        self.assertEqual(actual, [401])
        self.assertEqual(actual, list(legacy))

    def test_relation_fanout_does_not_duplicate_count_or_pages(self):
        for identifier in (501, 502, 503):
            self.book(identifier, title="Voyage", authors=("Writer One", "Writer Two"),
                      languages=("en", "fr"), formats=("text/plain", "text/html"),
                      subjects=("Travel diaries", "Travel essays"),
                      shelves=("Travel books", "Travel literature"))
        parameters = {"search": "voyage writer", "languages": "en,fr",
                      "mime_type": "text/", "topic": "travel"}
        # Count plus the page and eight prefetches remains bounded even when
        # every predicate matches multiple related rows on every book.
        with self.assertNumQueries(10):
            first = self.results(parameters)
        second = self.results(dict(parameters, page=2))
        self.assertEqual(first["count"], 3)
        self.assertEqual(second["count"], 3)
        self.assertIsNotNone(first["next"])
        self.assertIsNone(second["next"])
        self.assertEqual([book["id"] for book in first["results"]], [501, 502])
        self.assertEqual([book["id"] for book in second["results"]], [503])

    def test_combined_relation_filters_cannot_restore_blocked_books(self):
        matching = {"languages": ("en", "fr"), "formats": ("text/plain", "text/html"),
                    "subjects": ("Travel diaries",), "shelves": ("Travel books",)}
        self.book(601, **matching)
        self.book(602, **dict(matching, subjects=("Travel diaries", "Erotic fiction")), popularity=100)
        self.book(603, **dict(matching, shelves=("Travel books", "Pornography")), popularity=99)
        self.book(25305, **matching, popularity=98)
        self.book(604, **dict(matching, languages=("de",)))
        self.book(605, **dict(matching, formats=("application/pdf",)))
        self.book(606, **dict(matching, subjects=("History",), shelves=("History",)))
        self.assertEqual(self.result_ids({"languages": "EN,fr", "mime_type": "text/",
                                          "topic": "travel"}), [601])

    def test_only_first_four_search_terms_are_used(self):
        self.book(701, title="One two three four")
        self.book(702, title="One two three")
        search = "one two three four absent"
        self.assertEqual(self.result_ids({"search": search}), [701])
        self.assertEqual(self.result_ids({"search": search}), self.legacy_search_ids(search))

    def test_equal_popularity_pages_use_gutenberg_id_order(self):
        # Insert out of Gutenberg order so ordering by a database row ID cannot
        # accidentally satisfy the stable ordering contract across pages.
        for identifier in (803, 801, 802):
            self.book(identifier, popularity=10)
        first = self.results({})
        second = self.results({"page": 2})
        self.assertEqual([book["id"] for book in first["results"]], [801, 802])
        self.assertEqual([book["id"] for book in second["results"]], [803])
