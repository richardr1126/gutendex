from django.test import TestCase
from rest_framework.test import APIClient

from .models import Book, Bookshelf, Subject


class ContentPolicyTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def book(self, id, title="A book", subjects=(), shelves=(), popularity=1):
        book = Book.objects.create(gutenberg_id=id, title=title,
                                   media_type="Text", copyright=False,
                                   download_count=popularity)
        for name in subjects:
            book.subjects.add(Subject.objects.get_or_create(name=name)[0])
        for name in shelves:
            book.bookshelves.add(Bookshelf.objects.get_or_create(name=name)[0])
        return book

    def test_exclusions_apply_before_pagination_and_to_direct_access(self):
        self.book(25305, popularity=100)
        self.book(101, subjects=("Erotic fiction",), popularity=99)
        self.book(102, subjects=("Pornography",), popularity=98)
        self.book(103, shelves=("Category: Sexuality & Erotica",), popularity=97)
        self.book(104, title="An erotic novel", popularity=96)
        self.book(105, subjects=("Sadism -- Fiction",), popularity=95)
        self.book(106, subjects=("Romance fiction",), popularity=6)
        self.book(107, subjects=("War stories",), popularity=5)
        self.book(108, subjects=("Sex education",), popularity=4)
        response = self.client.get("/books/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual([book["id"] for book in response.data["results"]], [106, 107])
        self.assertIsNotNone(response.data["next"])
        self.assertEqual(response["X-OpenReader-Catalog-Policy"], "1")
        self.assertEqual(response["Cache-Control"], "no-store")
        for id in (25305, 101, 102, 103, 104, 105):
            self.assertEqual(self.client.get(f"/books/{id}/").status_code, 404)
            self.assertEqual(self.client.get("/books/", {"ids": id}).data["count"], 0)
        self.assertEqual(self.client.get("/books/", {"topic": "erotic"}).data["count"], 0)
        self.assertEqual(self.client.get("/books/", {"search": "erotic"}).data["count"], 0)
        self.assertEqual(self.client.get("/books/", {"page": 2}).data["results"][0]["id"], 108)
        self.assertEqual(self.client.get("/books/108/").status_code, 200)

    def test_multiple_subjects_cannot_reintroduce_an_excluded_book(self):
        self.book(200, subjects=("Romance fiction", "EROTIC stories"))
        self.assertEqual(self.client.get("/books/", {"topic": "Romance"}).data["count"], 0)
        self.assertEqual(self.client.get("/books/200/").status_code, 404)
