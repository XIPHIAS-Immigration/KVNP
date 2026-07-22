# AWS EC2 Demo Deployment

This is the cheap, practical deployment path for a short KVNP Passport Photo Studio demo.

## Recommended demo shape

Use one small x86_64 EC2 instance with Docker Compose:

- EC2: Ubuntu 24.04 LTS or Ubuntu 22.04 LTS, x86_64
- Instance size: `t3.medium` for reliability, `t3.small` only if you must cut cost
- Disk: 25-30 GB gp3
- Public access: ports `80` and `443`
- SSH: port `22`, restricted to your IP only
- Domain: GoDaddy `A` record pointing to the EC2 Elastic IP
- HTTPS: Caddy container, automatic Let's Encrypt certificate

Do not use Lambda for this app. The MediaPipe/OpenCV/model stack is too large and cold-start prone.

## Why not ARM / Graviton first?

`t4g.*` instances are cheaper, but they are ARM. MediaPipe Python dependency support is safer on x86_64, especially for a fast demo. Once the app is packaged and tested thoroughly, ARM can be evaluated separately.

## 1. Create EC2 instance

In AWS Console:

1. Launch instance.
2. AMI: Ubuntu Server LTS, x86_64.
3. Instance type: `t3.medium`.
4. Storage: 25-30 GB gp3.
5. Security group:
   - SSH `22` from your IP only.
   - HTTP `80` from anywhere.
   - HTTPS `443` from anywhere.
6. Create or choose an SSH key pair.
7. Launch.

Allocate and associate an Elastic IP so the domain does not change after reboot.

## 2. Point GoDaddy domain

In GoDaddy DNS:

- For root domain: create/edit `A` record named `@` to the Elastic IP.
- For subdomain: create/edit `A` record named e.g. `passport` to the Elastic IP.
- TTL: 600 seconds if available.

Example:

```text
passport.yourdomain.com  A  <EC2_ELASTIC_IP>
```

Wait a few minutes, then check:

```bash
nslookup passport.yourdomain.com
```

## 3. Install Docker on the EC2 instance

SSH into the instance:

```bash
ssh -i path/to/key.pem ubuntu@<EC2_ELASTIC_IP>
```

Install Docker and Compose plugin:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
newgrp docker
```

Check:

```bash
docker --version
docker compose version
```

## 4. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

## 5. Create production env

```bash
cp .env.example .env
openssl rand -base64 32
nano .env
```

Set:

```text
DOMAIN=passport.yourdomain.com
ACME_EMAIL=you@example.com
KVNP_SESSION_SECRET=<paste-long-random-secret>
```

Keep `HOST=0.0.0.0`, `PORT=4173`, and `KVNP_DATA_DIR=/app/data`.

## 6. Build and run

```bash
docker compose up -d --build
```

Watch logs:

```bash
docker compose logs -f app
docker compose logs -f caddy
```

Health check locally on the server:

```bash
curl http://127.0.0.1:4173/api/health
```

Public check after DNS resolves:

```bash
curl https://passport.yourdomain.com/api/health
```

Open:

```text
https://passport.yourdomain.com/?guest
```

## 7. Update deployment

```bash
git pull
docker compose up -d --build
```

## 8. Stop to save money

To stop the app containers but keep instance running:

```bash
docker compose down
```

To stop billing for compute, stop the EC2 instance from AWS Console. Do not leave unused Elastic IPs allocated after the demo.

## 9. Current production defaults

For the low-cost demo:

- CPU-only processing.
- MediaPipe + OpenCV enabled.
- MODNet only if `models/modnet.onnx` is added and license reviewed.
- GFPGAN / heavy face restoration not included in Docker requirements.
- Process user images in memory where possible.
- Local SQLite volume for short demo accounts/session state.

## 10. Troubleshooting

If HTTPS is not issued:

1. Confirm the GoDaddy `A` record points to the Elastic IP.
2. Confirm EC2 security group allows `80` and `443`.
3. Check Caddy logs:

```bash
docker compose logs -f caddy
```

If the app is slow on first start:

- First boot may download MediaPipe model files into `/app/models`.
- After that, Docker volume/container state should be faster.

If Docker build fails from memory pressure:

- Use `t3.medium` instead of `t3.small`.
