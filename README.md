# University of Mississippi Research Intelligence Dashboard

A comprehensive web-based research analytics dashboard for the University of Mississippi (Oxford, MS campus). Data is sourced from [OpenAlex](https://openalex.org) (free) and [Dimensions AI](https://www.dimensions.ai) (subscription).

---

## Prerequisites

- Python 3.11 or later
- pip
- A Dimensions AI API key — request one at [dimensions.ai/products/all-products/dimensions-api/](https://www.dimensions.ai/products/all-products/dimensions-api/)

---

## Setup

```bash
git clone <your-repo-url>
cd um-research-dashboard

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — add your Dimensions API key and a random FLASK_SECRET_KEY

# Start the development server
flask run
```

Open your browser at http://127.0.0.1:5000.

---

## Environment Variables (`.env`)

| Variable | Description |
|---|---|
| `DIMENSIONS_API_KEY` | Your Dimensions AI API key |
| `OPENALEX_EMAIL` | Email for OpenAlex polite-pool requests (higher rate limit) |
| `FLASK_SECRET_KEY` | Random string used for Flask session signing |
| `FLASK_ENV` | `development` or `production` |
| `CACHE_DB_PATH` | Path for the SQLite cache file (default: `cache.db`) |

---

## Deployment to Apache / Nginx

### 1. Install Gunicorn

```bash
pip install gunicorn
```

### 2. Start with Gunicorn

```bash
gunicorn -w 4 -b 127.0.0.1:8000 app:app
```

### 3. Nginx reverse-proxy config

```nginx
server {
    listen 80;
    server_name research.olemiss.edu;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    location /static/ {
        alias /var/www/um-research-dashboard/static/;
        expires 7d;
    }
}
```

### 4. systemd service

Create `/etc/systemd/system/um-dashboard.service`:

```ini
[Unit]
Description=UM Research Dashboard
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/um-research-dashboard
EnvironmentFile=/var/www/um-research-dashboard/.env
ExecStart=/var/www/um-research-dashboard/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable um-dashboard
sudo systemctl start um-dashboard
```

---

## Refreshing the Cache

The app caches API responses in `cache.db` (SQLite) to minimise API calls.

- **Force re-fetch a single endpoint:** append `?refresh=1` to any API route, e.g.
  `curl http://localhost:5000/api/publications/by-year?refresh=1`
- **Check cache health:** visit `/api/cache-status`
- **Clear all cache:** delete `cache.db` and restart the app
  ```bash
  rm cache.db && flask run
  ```

Cache TTLs:
- Most endpoints: 24 hours
- Historical/field/patent data: 7 days

---

## Data Sources

### OpenAlex

[OpenAlex](https://openalex.org) is a fully open catalogue of scholarly works, authors, institutions, and more. It covers ~250 million works.

**Strengths:** Free, open, no authentication required, extensive metadata, updated daily.
**Limitations:** Some older or grey literature may be missing; institutional disambiguation is automated and occasionally imprecise.

UM Oxford is identified using ROR ID **https://ror.org/02bdmhw89**. At startup the app verifies that the resolved institution has `geo.city == "Oxford"` and `geo.region == "Mississippi"` to prevent confusion with UMMC (Jackson).

### Dimensions AI

[Dimensions](https://www.dimensions.ai) is a comprehensive research information system covering publications, grants, clinical trials, patents, and datasets.

**Strengths:** Broad coverage of grants and clinical trials, integrated across research outputs.
**Limitations:** Subscription required; grant/trial data may lag real-time by days to weeks.

UM Oxford is queried using GRID ID **grid.266226.6**.

> Publication counts from OpenAlex and Dimensions will differ. This is expected — both systems use different coverage rules and disambiguation methods. Both are valid estimates.

---

## Institution Identity

| Identifier | Value |
|---|---|
| ROR ID | https://ror.org/02bdmhw89 |
| OpenAlex ID | I145858726 (verified at startup) |
| Dimensions GRID | grid.266226.6 |

**Important:** The University of Mississippi Medical Center (UMMC, Jackson) has a separate ROR and OpenAlex ID. This dashboard filters strictly to the Oxford campus only.

---

## Dashboard Tabs

| Tab | Data Source | Description |
|---|---|---|
| Overview | Both | Key stats: publications, citations, h-index, OA %, grants |
| Publications | OpenAlex | Yearly trend, type breakdown, paginated list |
| Research Fields | OpenAlex | Top 20 fields by publication count |
| Open Access | OpenAlex | OA status breakdown and yearly trend |
| Authors | OpenAlex | Top 25 authors, sortable, with works modal |
| Grants & Funding | Dimensions AI | Funder breakdown, yearly trend, paginated list |
| Clinical Trials | Dimensions AI | Phase breakdown, searchable list |
| Patents | Dimensions AI | Yearly filing trend, paginated list |
| Collaborations | OpenAlex | Top collaborating institutions and countries |
| Journals | OpenAlex | Top 20 publication venues |

---

## License

MIT — see LICENSE file.
