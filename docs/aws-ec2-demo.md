# AWS EC2 Demo Deployment

This runbook covers both the inexpensive CPU demo and the quality GPU deployment.

## Recommended demo shape

Use one small x86_64 EC2 instance with Docker Compose:

- EC2: Ubuntu 24.04 LTS or Ubuntu 22.04 LTS, x86_64
- Instance size: `t3.medium` for reliability, `t3.small` only if you must cut cost
- Disk: 25-30 GB gp3
- Public access: ports `80` and `443`
- SSH: port `22`, restricted to your IP only
- Domain: GoDaddy `A` record pointing to the EC2 Elastic IP
- HTTPS: Caddy container, automatic Let's Encrypt certificate

The CPU path is suitable for layout, rules, accounts, and light testing. The
BiRefNet quality matte measured about 20-22 seconds per portrait on the current
development CPU. For a public demo where background removal must feel immediate,
use the GPU path below.

## Recommended quality deployment

Use `g4dn.xlarge` with an AWS Deep Learning Base GPU AMI (Ubuntu), x86_64:

- 1 NVIDIA T4 GPU with 16 GiB VRAM
- 4 vCPU and 16 GiB system RAM
- 30-40 GB gp3 root disk
- the same ports, Elastic IP, DNS, and Caddy setup as the CPU instance

The app uses ONNX Runtime CUDA only for the quality matte. MediaPipe, OpenCV,
validation, accounts, and Caddy remain on CPU. Stop the instance whenever the
demo is not being used.

Do not use Lambda for this app. The MediaPipe/OpenCV/model stack is too large and cold-start prone.

## Why not ARM / Graviton first?

`t4g.*` instances are cheaper, but they are ARM. MediaPipe Python dependency support is safer on x86_64, especially for a fast demo. Once the app is packaged and tested thoroughly, ARM can be evaluated separately.

## 1. Create EC2 instance

In AWS Console:

1. Launch instance.
2. AMI: Ubuntu Server LTS, x86_64.
3. Instance type: `t3.medium` for CPU, or `g4dn.xlarge` for quality matting.
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

For `g4dn.xlarge`, first confirm the AMI driver is active:

```bash
nvidia-smi
```

Then install and configure the NVIDIA Container Toolkit using NVIDIA's current
Ubuntu instructions. After installation, configure Docker and verify access:

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu24.04 nvidia-smi
```

Do not continue with the GPU Compose file until that container-level check works.

## 4. Clone the repo

```bash
git clone https://github.com/XIPHIAS-Immigration/KVNP.git
cd KVNP
```

## 5. Create production env

```bash
cp .env.example .env
openssl rand -base64 32
nano .env
```

Set:

```text
DOMAIN=passport.kvnp.ca
ACME_EMAIL=you@example.com
KVNP_SESSION_SECRET=<paste-long-random-secret>
```

Keep `HOST=0.0.0.0`, `PORT=4173`, and `KVNP_DATA_DIR=/app/data`.

## 6. Build and run

CPU deployment:

```bash
docker compose up -d --build
```

NVIDIA GPU deployment:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
```

Watch logs:

```bash
docker compose logs -f app
docker compose logs -f caddy
```

Health check inside the app container:

```bash
docker compose exec -T app curl -fsS http://127.0.0.1:4173/api/health
```

Public check after DNS resolves:

```bash
curl -fsS https://passport.kvnp.ca/api/health
```

On a GPU deployment, verify CUDA inside the app container:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml exec -T app \
  python -c "import onnxruntime as ort; print(ort.get_available_providers())"
```

The output must contain `CUDAExecutionProvider`. Upload one portrait, then check
`/api/health`; the active BiRefNet provider should be CUDA rather than CPU.

Open:

```text
https://passport.kvnp.ca/
```

## 7. Update deployment

```bash
cd ~/KVNP
git pull --ff-only origin main
docker compose up -d --build --remove-orphans
docker compose ps
docker compose exec -T app curl -fsS http://127.0.0.1:4173/api/health
curl -fsS https://passport.kvnp.ca/api/health
```

For the GPU deployment, use the two-file form for the rebuild and app exec:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build --remove-orphans
docker compose -f compose.yaml -f compose.gpu.yaml exec -T app \
  curl -fsS http://127.0.0.1:4173/api/health
```

The ignored `.env` file and the `kvnp_data` Docker volume remain in place during
this update. If the public check returns `502`, inspect the application first:

```bash
docker compose logs --tail=100 app
docker compose logs --tail=100 caddy
```

## 8. Stop to save money

To stop the app containers but keep instance running:

```bash
docker compose down
```

To stop billing for compute, stop the EC2 instance from AWS Console. Do not leave unused Elastic IPs allocated after the demo.

## 9. Current production defaults

For the low-cost CPU demo:

- CPU-only processing.
- MediaPipe + OpenCV enabled.
- BiRefNet Portrait is downloaded into the persistent model volume and falls
  back to MODNet or MediaPipe if it cannot load.
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

- First boot downloads and verifies the roughly 1 GB BiRefNet weight plus the
  smaller MediaPipe models into `/app/models`.
- After that, Docker volume/container state should be faster.

If a GPU deployment reports only `CPUExecutionProvider`:

1. Run `nvidia-smi` on the host.
2. Run the NVIDIA CUDA test container from section 3.
3. Confirm the deployment used both `compose.yaml` and `compose.gpu.yaml`.
4. Check `docker compose -f compose.yaml -f compose.gpu.yaml logs --tail=150 app`.

If Docker build fails from memory pressure:

- Use `t3.medium` instead of `t3.small`.
