# Prometheus metrics

Menshen's backend ships an **opt-in** instrumentation,
[django-prometheus](https://github.com/django-commons/django-prometheus). It is
**disabled by default**: when `PROMETHEUS_METRICS_ENABLED` is unset,
`django_prometheus` is not in `INSTALLED_APPS`, its middlewares are not
installed, the database engine is left alone and `/metrics` is not routed.

## Enabling it

```bash
PROMETHEUS_METRICS_ENABLED=True
PROMETHEUS_API_KEY=<a long random secret>   # or PROMETHEUS_API_KEY_FILE
```

The application **refuses to start** with the metrics enabled and no key: the
endpoint would otherwise answer to anybody.

Then scrape `GET /metrics` with the key as a bearer token:

```yaml
scrape_configs:
  - job_name: menshen-backend
    scheme: https
    metrics_path: /metrics
    authorization:
      type: Bearer
      credentials_file: /etc/prometheus/menshen-api-key
    static_configs:
      - targets: ["metrics.menshen.example.com"]
```

### Settings

| Setting                                  | Default | Description                                                                                                    |
| ---------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------- |
| `PROMETHEUS_METRICS_ENABLED`             | `False` | Install django-prometheus and serve `/metrics`                                                                 |
| `PROMETHEUS_API_KEY`                     | `None`  | Bearer token required on `/metrics` (also readable from a file with `PROMETHEUS_API_KEY_FILE`)                 |
| `PROMETHEUS_METRICS_SSL_REDIRECT_EXEMPT` | `False` | Take `/metrics` out of the redirect to https (`SECURE_SSL_REDIRECT`), for a scraper reaching the pods directly |
| `PROMETHEUS_DB_METRICS_ENABLED`          | `True`  | Also count and time the SQL queries, with django-prometheus' instrumented PostgreSQL engine                    |
| `PROMETHEUS_MULTIPROC_DIR`               | `None`  | Directory the worker processes share their metrics in (see [uvicorn workers](#uvicorn-workers))                |

## What is measured

- HTTP requests: counts and latency histograms, labelled by **view name**,
  method and status (`django_http_requests_latency_seconds_by_view_method`,
  `django_http_responses_total_by_status_view_method_total`, ...).
- SQL (unless `PROMETHEUS_DB_METRICS_ENABLED=False`): queries, errors and query
  duration (`django_db_execute_total`, `django_db_query_duration_seconds`,
  ...). With `DB_PSYCOPG_POOL_ENABLED`, `django_db_new_connections_total` counts
  the connections taken from the pool, not the connections opened to Postgres.

No label ever carries a path, a user or a token. A request that matches no
route is counted under `<unnamed view>`.

Every sample carries a `hostname` label (the pod name in Kubernetes), see
[Several replicas](#several-replicas-behind-one-address).

## How the endpoint is protected

| Layer                     | What it guarantees                                                                                                                                                             |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Off by default            | Nothing is installed, and `/metrics` is a 404, unless the deployment asks for it                                                                                               |
| Bearer token              | `metrics.middleware.PrometheusAuthMiddleware` refuses anything but `Authorization: Bearer <PROMETHEUS_API_KEY>`, compared in constant time. It fails closed: no key, no answer |
| First middleware          | A refused call stops there: no session is created, no database or cache access is made                                                                                         |
| Dedicated ingress (chart) | One exact path on a host of its own, where the callers can be filtered by address                                                                                              |
| Labels                    | No path, user or token leaves the application                                                                                                                                  |

> [!WARNING]
> The application ingress of the Helm chart publishes every path under
> `ingress.path` (`/` by default): `/metrics` is then reachable through it too,
> protected by the bearer token only. Block it at the ingress controller level
> if you want it to be reachable through the [dedicated
> ingress](#a-prometheus-outside-of-the-cluster) or the pods only.

The key is a long-lived shared secret, which is what a Prometheus scraper can
present. Treat it as such: give it through `PROMETHEUS_API_KEY_FILE` or a
Kubernetes secret, keep TLS on wherever it travels, and rotate it by changing
the value on both sides.

In production the endpoint follows `SECURE_SSL_REDIRECT` like every other path:
a scrape over plain http is redirected to https, so that the key never travels
in clear. `PROMETHEUS_METRICS_SSL_REDIRECT_EXEMPT=True` lifts that for
`/metrics` only, for a scraper that reaches the process past the proxy
terminating TLS, see [several replicas](#several-replicas-behind-one-address).

## uvicorn workers

uvicorn runs several worker processes (`WEB_CONCURRENCY`) and a scrape is
answered by one of them. The workers therefore all write their numbers to one
directory (prometheus_client's multiprocess mode), and whichever answers adds
them up. Nothing has to be configured: the directory defaults to
`<tmp>/menshen-prometheus-<uid>`, is created with mode `0700`, and the
application refuses a directory owned by another user or a symbolic link. Set
`PROMETHEUS_MULTIPROC_DIR` to put it elsewhere: it must be writable, and local
to the host or the pod, it is **not** shared between replicas.

Known limit: uvicorn recycles its workers (`--limit-max-requests`) and has no
hook to tell when one is gone. Every new worker writes new files, and the files
of the workers that are gone must stay: their counters are part of the totals.
The directory grows, and the scrape gets slower, until the container is
replaced. Watch `scrape_duration_seconds` on long runs. Outside of a container,
empty the directory when the application is stopped.

## Several replicas behind one address

A scrape that goes through a load balancer (an ingress in front of several
backend pods) is answered by a different replica each time. The `hostname`
label keeps the replicas apart: each has its own series, and its counters never
go backwards. Each series is only sampled when its replica happens to answer,
so with `N` replicas expect one sample every `N` scrapes on average: use a short
scrape interval and rate windows of several minutes, and aggregate with
`sum without (hostname) (rate(...[5m]))`.

This degrades as the number of replicas grows. A Prometheus running inside the
cluster should scrape each pod directly instead: same path, same bearer token,
one target per pod. The chart builds the `ServiceMonitor` or `PodMonitor` for
it, see [below](#kubernetes-helm-chart). Such a scrape reaches the pod over
plain http, past the ingress that terminates TLS, and the Production settings
redirect it to https like anything else, where it gets nothing. Set
`PROMETHEUS_METRICS_SSL_REDIRECT_EXEMPT=True` to take `/metrics` out of that
redirect, the way the heartbeats are; the pod's own address is already in
`ALLOWED_HOSTS`. Leave it off wherever the application is reached directly,
without a proxy in front: the redirect is then what keeps the bearer token off
the wire in clear.

## Kubernetes (Helm chart)

```yaml
backend:
  metrics:
    enabled: true
  envVars:
    PROMETHEUS_API_KEY:
      secretKeyRef:
        name: backend
        key: PROMETHEUS_API_KEY
```

`backend.metrics.enabled` sets `PROMETHEUS_METRICS_ENABLED` and
`PROMETHEUS_METRICS_SSL_REDIRECT_EXEMPT` on the backend container, since a pod
is only ever scraped over plain http. A value given in `backend.envVars` or
`backend.django.envVars` still wins.

### Prometheus Operator, inside the cluster

```yaml
serviceMonitor:
  enabled: true
  labels:
    release: kube-prometheus-stack # whatever your Prometheus selects monitors by
```

`serviceMonitor.enabled` (or `podMonitor.enabled`, or both) creates a monitor
scraping every backend pod on the `http` port and the `/metrics` path. Each pod
is a target of its own, so every sample of every replica is taken at every
interval, nothing goes through an ingress, and the `hostname` label is simply
the pod.

The scrape presents the bearer token, which the Prometheus Operator reads from
the Secret `PROMETHEUS_API_KEY` comes from in the `envVars` above (or from the
one named in `backend.metrics.apiKeySecret`, for a token given as
`PROMETHEUS_API_KEY_FILE`). A token that is not in a Secret is refused at render
time. That Secret has to live in the namespace of the monitors, and the service
account of the operator be allowed to read it.

A `ServiceMonitor` finds the pods through their Service, a `PodMonitor` through
their labels; they give the same targets. `interval`, `scrapeTimeout`,
`honorLabels`, `relabelings`, `metricRelabelings`, `labels`, `annotations` and
`namespace` are the same on both.

### A Prometheus outside of the cluster

```yaml
backend:
  envVars:
    DJANGO_ALLOWED_HOSTS: menshen.example.com,metrics.menshen.example.com

ingressMetrics:
  enabled: true
  host: metrics.menshen.example.com
  annotations:
    nginx.ingress.kubernetes.io/whitelist-source-range: "203.0.113.10/32"
```

`ingressMetrics` routes the exact path `/metrics` of that host to the backend
and nothing else. Its host has to be in `DJANGO_ALLOWED_HOSTS`. What is said
above about [several replicas](#several-replicas-behind-one-address) applies:
prefer the monitors whenever the Prometheus can reach the pods.
