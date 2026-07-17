# Deploying to Hetzner (Docker)

On every push to `main`, [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml):

1. **build** — builds the Docker image and pushes it to GitHub Container Registry (GHCR).
2. **deploy** — SSHes into the server, pulls the new image, runs migrations, and `docker compose up -d`.

The **app code lives in the image**; only secrets/config (`.env`, `config/*.json`) live
on the server. Do the one-time setup below once, then `git push` deploys.

---

## 1. Create the server
- Hetzner Cloud → new server, **Ubuntu 24.04**, add your personal SSH key.
- `ssh root@SERVER_IP`.

## 2. Install Docker (on the server)
```bash
curl -fsSL https://get.docker.com | sh
docker compose version   # confirm the compose plugin is present
apt install -y git
```

## 3. Get the deploy files
The server needs `docker-compose.yml`, `deploy/Caddyfile`, `.env`, and `config/`.
Easiest is to clone the repo (the image is pulled separately from GHCR):
```bash
git clone https://github.com/YOUR_USER/ensight-backend.git /opt/ensight-backend
cd /opt/ensight-backend
```
Private repo? Add a read-only **deploy key** (`ssh-keygen` → add the `.pub` under
GitHub → repo → Settings → Deploy keys) and clone via SSH.

## 4. Add secrets + config (NOT in git)
```bash
cd /opt/ensight-backend
nano .env                     # your full .env
mkdir -p config
nano config/ensight-sa.json   # your Google service-account JSON
chmod 600 .env config/ensight-sa.json
```
Add **one line** to `.env` so compose knows which image to pull (lowercase!):
```
IMAGE=ghcr.io/your-github-user/ensight-backend:latest
```

## 5. First run (manual, once)
```bash
# log in so the server can pull the private image (use a GitHub PAT with read:packages)
echo YOUR_GITHUB_PAT | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
docker compose pull
docker compose run --rm api python migrate.py   # create the DB tables
docker compose up -d
docker compose ps
```

## 6. Domain + HTTPS
Point an A record (e.g. `api.yourdomain.com`) at the server IP, set it in
[`deploy/Caddyfile`](Caddyfile), then:
```bash
docker compose up -d   # Caddy fetches a TLS cert automatically
```
API is now live at `https://api.yourdomain.com`, WebSockets included.

---

## 7. Wire up auto-deploy (GitHub Actions)
Generate a CI SSH key and authorize it on the server:
```bash
# on your laptop
ssh-keygen -t ed25519 -f ~/.ssh/hetzner_deploy -N ""
ssh-copy-id -i ~/.ssh/hetzner_deploy.pub root@SERVER_IP
```
GitHub → repo → **Settings → Secrets and variables → Actions** → add:

| Secret | Value |
|--------|-------|
| `HETZNER_HOST` | server IP (or domain) |
| `HETZNER_USER` | `root` |
| `HETZNER_PORT` | `22` |
| `HETZNER_SSH_KEY` | contents of the **private** key `~/.ssh/hetzner_deploy` |

`GITHUB_TOKEN` (used to push/pull the image) is provided automatically — no secret needed.

Push to `main` → it builds, pushes, and deploys.

---

## Notes
- **Secrets never go in the image or git.** `.env` + `config/*.json` are gitignored and
  mounted at runtime (`env_file` + a volume).
- **Vector store persists** across deploys via the `chroma_data` volume.
- **GHCR image visibility** follows the repo. For a private repo the server login in
  step 5 is required (the Action's `GITHUB_TOKEN` handles pulls during deploys).
- **Logs:** `docker compose logs -f api`
- **Manual deploy:** `cd /opt/ensight-backend && docker compose pull && docker compose up -d`
- **Memory:** the image bundles the RAG/voice stack — give the server ≥ 2 GB RAM. Raise
  `--workers` in the `Dockerfile` only if you have headroom.
