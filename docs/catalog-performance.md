# Catalog query performance

The book API filters each relationship through a set of matching book IDs,
so multiple authors, subjects, shelves or formats cannot multiply book rows.
Each search term and author-year bound has its own membership predicate:
different authors may satisfy different terms or bounds, as before.
Content exclusions resolve matching subject and shelf IDs once instead of
running nine correlated checks for every candidate book. Exact result counts
remain part of the API; no approximate counts or response cache are used.

A nonempty page uses ten database queries: count, page retrieval, and eight
relationship prefetches. Formats and summaries consume the same prefetch cache
as the other relationships. Default popularity ordering breaks equal download
counts by Gutenberg ID, keeping page boundaries consistent between requests
when the catalog is unchanged. Explicit ascending/descending sorting retains
its previous database-ID behavior.

## Validation

Run `python manage.py test books --settings=books.test_settings`.
The API regression tests cover multi-author search/year semantics, authorless
titles, relationship fanout, pagination, combined filters and content exclusions.
Serialization tests cover the existing JSON shape and bounded query counts.

On October 7, 2026, a one-shot read-only process on the Raspberry Pi cluster
queried the live 79,557-book PostgreSQL catalog with the proposed view and
serializer code. Complete response generation, including JSON rendering,
took 0.807 s for public-domain English books (62,305 matches), 0.659 s for
"Pride Prejudice" (6 matches), 0.667 s for "Dickens" (231 matches), and
0.727 s for English books matching topic "children" (7,635 matches).
Each nonempty request used ten queries. Blocked IDs 25305 and 30254 yielded
zero matches. These are warm database/server measurements, excluding network,
reverse-proxy transport and concurrency; they do not establish cold-start or
load-test latency. The earlier public "Pride Prejudice" request took 42.4 s,
including transport, so deployment still needs public-endpoint verification.

No database migration or reimport is needed. Pin the published image in the
chart, sync Argo CD, then measure through the public hostname and repeat the
policy checks in `content-policy.md`. If latency remains unacceptable under
load, profile the deployed count and page plans before adding indexes or cache.
