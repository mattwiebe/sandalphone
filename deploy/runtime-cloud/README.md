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
ssh hetzner 'cd /opt/levi-runtime-cloud && python3 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install .'
ssh hetzner 'cp /opt/levi-runtime-cloud/.env.example /opt/levi-runtime-cloud/.env'
scp deploy/runtime-cloud/levi-runtime-cloud.service hetzner:/tmp/levi-runtime-cloud.service
ssh hetzner 'sudo mv /tmp/levi-runtime-cloud.service /etc/systemd/system/levi-runtime-cloud.service && sudo systemctl daemon-reload && sudo systemctl enable --now levi-runtime-cloud.service'
```

## Verify

```bash
ssh hetzner 'systemctl status levi-runtime-cloud.service --no-pager'
ssh hetzner 'curl -s http://127.0.0.1:8787/health'
```
