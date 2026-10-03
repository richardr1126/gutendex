# Gutendex Helm Chart

A Helm chart for Gutendex based on the `bjw-s` [`app-template`](https://github.com/bjw-s/helm-charts/tree/main/charts/other/app-template).

It runs three things:

- **`main`**, the API: gunicorn behind a Traefik ingress at
  `gutendex.richardr.dev`. external-dns publishes the record through
  Cloudflare with proxying on, and Cloudflare terminates HTTPS.
- **`postgres`**, a dedicated PostgreSQL 17 StatefulSet on a 10 Gi
  `local-path` volume. Nothing pins it to a node, but a `local-path` volume
  belongs to the node it was first created on, so the database stays wherever
  it first lands.
- **`updatecatalog`**, a nightly CronJob that downloads Project Gutenberg's RDF
  catalog and loads it into the database.

The API requires a key. Clients send it as `X-API-Key: <key>` or
`Authorization: Bearer <key>`; `/healthz` is the only open path.

## Prerequisites

- [Helm](https://helm.sh) >= 3.0
- Kubernetes cluster with Traefik, external-dns (Cloudflare) and a
  `local-path` storage class
- The image `ghcr.io/richardr1126/gutendex`, published by
  `.github/workflows/docker-publish.yml` on every push to `master`

## Setup

The `app-template` dependency is vendored in `charts/`. To refresh it:

```bash
helm repo add bjw-s https://bjw-s-labs.github.io/helm-charts
helm repo update
cd charts/gutendex
helm dependency update
```

## Installation

1. Create the secret. Copy `charts/.env.example` to `charts/.env`, fill it in,
   then:

   ```bash
   ./charts/create_secrets.sh
   ```

2. Install. **The release must be named `gutendex`**: the API finds the
   database at `gutendex-postgres`, the Service name app-template derives from
   the release name. A different name needs `DATABASE_HOST` changed to match.

   ```bash
   helm upgrade --install gutendex charts/gutendex -n default
   ```

   Or through ArgoCD, which syncs the chart from `master`:

   ```bash
   kubectl apply -f charts/argocd.yaml
   ```

   then sync it from the ArgoCD UI. The secret is still made by
   `create_secrets.sh`; ArgoCD does not manage it.

3. Load the catalog. The database starts empty and the CronJob only runs at
   09:00 UTC, so start the first import by hand:

   ```bash
   kubectl create job --from=cronjob/gutendex-updatecatalog gutendex-initial-import
   kubectl logs -f job/gutendex-initial-import
   ```

   Until it finishes, `/books/` returns only the books loaded so far.

## Checking it

```bash
curl -s https://gutendex.richardr.dev/healthz
curl -s -H "X-API-Key: $KEY" "https://gutendex.richardr.dev/books/?copyright=false&languages=en" | head -c 300
```

The first should say `{"status": "ok"}` with no key. The second should list
books, and its `next` link should start with `https://`.

## Configuration

All standard options from `app-template` are available under `app-template:`.
Settings shared by every Gutendex container are the `x-gutendex-env` anchor at
the top of `values.yaml`:

- `ALLOWED_HOSTS`: the public host name, plus `localhost` for the probes.
- `DATABASE_*`: the in-chart Postgres. The password comes from the secret.
- `FORCE_HTTPS`: makes pagination links `https://` behind Cloudflare.

The secret `gutendex-secrets` holds:

- `SECRET_KEY`: Django's signing key.
- `DATABASE_PASSWORD`: read by Postgres only when its volume is first
  initialised. Changing it later does not change the database's password.
- `API_KEYS`: comma-separated. List the new and the old key together while
  clients move over, then remove the old one and rerun `create_secrets.sh`.
  Pods read the secret when they start, so restart the API afterwards:
  `kubectl rollout restart deployment/gutendex-main`. (The chart carries the
  Stakater Reloader annotation, as KittenTTS's does, but this cluster has no
  Reloader running to act on it.)

Leaving `API_KEYS` empty makes the API public, as upstream Gutendex is.
