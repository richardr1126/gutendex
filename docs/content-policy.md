# OpenReader catalog policy

The API excludes erotic/pornographic and sadism-labelled subjects and shelves,
the entire Sexuality & Erotica shelf, titles labelled erotic/pornographic,
and known explicit IDs recorded with reasons in `books/content_policy.py`.
The filter applies before counting and pagination and to individual records.
Query parameters cannot switch it off. Nightly metadata imports do not erase
these rules. No database migration or catalog reimport is required.

This is a conservative metadata exclusion filter, not a full-text assessment,
per-book age rating, or guarantee of App Store approval. Unlabelled explicit
content can be missed. Review exclusion matches and add IDs as needed. The
remaining catalog can include literary violence, horror, profanity, alcohol,
medical information and non-graphic sexual themes; declare these accurately
in App Store Connect. The intended initial app rating is 13+, subject to the
questionnaire and Apple review. This change introduces no user-age gate.

Responses carry `X-OpenReader-Catalog-Policy: 1` and `Cache-Control: no-store`.
OpenReader requires the marker and rechecks the filtered book detail before
starting a download. Old app versions do not check it, but the server still
filters their requests. The marker identifies an enforcing server, not proof
that every book has been reviewed.

## Verification

Run `python manage.py test books --settings=books.test_settings` with the
requirements installed. Tests use in-memory SQLite, never production Postgres.
After deployment, verify `/books/25305/` and `/books/30254/` return 404, searches
for those IDs have zero results, `/books/1342/` still succeeds, and list/detail
responses include the policy marker. Use the existing API key without putting
it in URLs or logs. Purge any pre-deployment proxy cache if the proxy ignores
origin Cache-Control, and verify through the public reverse-proxy hostname.

## Deploy this change

The chart pins `ghcr.io/richardr1126/gutendex:sha-768c796`, the tested
policy build published by GitHub Actions. Refresh the `gutendex` Argo CD
application to the latest master, then sync. Changing the image tag rolls API
replicas and updates the nightly importer without modifying the database.
Wait for Healthy/Synced, then run the public-endpoint checks above. A plain
sync of an unchanged `latest` tag would not restart existing pods.
