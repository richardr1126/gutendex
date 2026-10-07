from django.test import TestCase

from .models import Book, Bookshelf, Format, Language, Person, Subject, Summary
from .serializers import BookSerializer


class BookSerializationTests(TestCase):
    # Keep this contract explicit: adding a serialized relation must not quietly
    # restore a per-book query on a full catalog page.
    related_fields = (
        "authors", "editors", "translators", "bookshelves", "languages",
        "subjects", "format_set", "summary_set",
    )

    @classmethod
    def setUpTestData(cls):
        author = Person.objects.create(name="Author", birth_year=1800, death_year=1870)
        editor = Person.objects.create(name="Editor")
        translator = Person.objects.create(name="Translator", birth_year=1900)
        shelves = [Bookshelf.objects.create(name=name) for name in ("Zulu", "Alpha")]
        languages = [Language.objects.create(code=code) for code in ("fr", "en")]
        subjects = [Subject.objects.create(name=name) for name in ("Z subject", "A subject")]
        for index in range(32):
            book = Book.objects.create(
                gutenberg_id=1000 + index, title="Book %d" % index,
                copyright=False, media_type="Text", download_count=100 - index,
            )
            book.authors.add(author)
            book.editors.add(editor)
            book.translators.add(translator)
            book.bookshelves.add(*shelves)
            book.languages.add(*languages)
            book.subjects.add(*subjects)
            Format.objects.create(book=book, mime_type="text/plain", url="https://example.com/old.txt")
            Format.objects.create(book=book, mime_type="text/html", url="https://example.com/book.html")
            Format.objects.create(book=book, mime_type="text/plain", url="https://example.com/book.txt")
            Summary.objects.create(book=book, text="Z summary")
            Summary.objects.create(book=book, text="A summary")

    def books(self):
        return Book.objects.order_by("gutenberg_id").prefetch_related(*self.related_fields)

    def test_full_page_uses_one_query_per_relation(self):
        with self.assertNumQueries(9):
            data = BookSerializer(self.books(), many=True).data
        self.assertEqual(len(data), 32)
        self.assertEqual([book["id"] for book in data], list(range(1000, 1032)))

    def test_serializing_a_prefetched_page_issues_no_queries(self):
        books = list(self.books())
        with self.assertNumQueries(0):
            data = BookSerializer(books, many=True).data
        self.assertEqual(len(data), 32)
        self.assertTrue(all(book["summaries"] == ["A summary", "Z summary"] for book in data))
        self.assertTrue(all(book["formats"]["text/plain"] == "https://example.com/book.txt" for book in data))

    def test_prefetch_preserves_the_complete_json_shape(self):
        expected = {
            "id": 1000, "title": "Book 0",
            "authors": [{"name": "Author", "birth_year": 1800, "death_year": 1870}],
            "summaries": ["A summary", "Z summary"],
            "editors": [{"name": "Editor", "birth_year": None, "death_year": None}],
            "translators": [{"name": "Translator", "birth_year": 1900, "death_year": None}],
            "subjects": ["A subject", "Z subject"], "bookshelves": ["Alpha", "Zulu"],
            "languages": ["en", "fr"], "copyright": False, "media_type": "Text",
            "formats": {"text/plain": "https://example.com/book.txt", "text/html": "https://example.com/book.html"},
            "download_count": 100,
        }
        self.assertEqual(BookSerializer(Book.objects.get(gutenberg_id=1000)).data, expected)
        prefetched = self.books().get(gutenberg_id=1000)
        with self.assertNumQueries(0):
            self.assertEqual(BookSerializer(prefetched).data, expected)

    def test_empty_relations_preserve_empty_collections_and_nulls(self):
        book = Book.objects.create(gutenberg_id=2000, media_type="Text")
        expected = {
            "id": 2000, "title": None, "authors": [], "summaries": [],
            "editors": [], "translators": [], "subjects": [], "bookshelves": [],
            "languages": [], "copyright": None, "media_type": "Text",
            "formats": {}, "download_count": None,
        }
        self.assertEqual(BookSerializer(book).data, expected)
        prefetched = self.books().get(gutenberg_id=2000)
        with self.assertNumQueries(0):
            self.assertEqual(BookSerializer(prefetched).data, expected)
