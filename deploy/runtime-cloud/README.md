# Runtime Cloud Deployment

This deploys the dedicated LiveKit/Pipecat cloud runtime to Hetzner.

## Layout

- app dir: `/opt/levi-runtime-cloud`
- service: `levi-runtime-cloud.service`
- port: `8787`

## Install

```bash
ssh hetzner 'sudo mkdir -p /opt/levi-runtime-cloud && sudo chown -R sandalphone:sandalphone /opt/levi-runtime-cloud'
rsync -av runtime-cloud/ hetzner:/opt/levi-runtime-cloud/
ssh hetzner 'sudo -u sandalphone sh -lc "curl -LsSf https://astral.sh/uv/install.sh | sh"'
ssh hetzner 'sudo install -m 0755 /home/sandalphone/.local/bin/uv /usr/local/bin/uv'
ssh hetzner 'sudo -u sandalphone sh -lc "export PATH=\$HOME/.local/bin:\$PATH && cd /opt/levi-runtime-cloud && uv sync --frozen"'
ssh hetzner 'cp /opt/levi-runtime-cloud/.env.example /opt/levi-runtime-cloud/.env'
scp deploy/runtime-cloud/levi-runtime-cloud.service hetzner:/tmp/levi-runtime-cloud.service
scp deploy/runtime-cloud/start-runtime-cloud.sh hetzner:/tmp/start-runtime-cloud.sh
ssh hetzner 'sudo mv /tmp/start-runtime-cloud.sh /usr/local/bin/start-runtime-cloud.sh && sudo chmod +x /usr/local/bin/start-runtime-cloud.sh'
ssh hetzner 'sudo mv /tmp/levi-runtime-cloud.service /etc/systemd/system/levi-runtime-cloud.service && sudo systemctl daemon-reload && sudo systemctl enable --now levi-runtime-cloud.service'
```

## Verify

```bash
ssh hetzner 'systemctl status levi-runtime-cloud.service --no-pager'
ssh hetzner 'curl -s http://127.0.0.1:8787/health'
```

## Required Provider Env

Set these in `/opt/levi-runtime-cloud/.env` before starting the trusted-leg bot:

```bash
ASSEMBLYAI_API_KEY=...
DEEPL_API_KEY=...
CARTESIA_API_KEY=...
CARTESIA_VOICE_ID=...
```
