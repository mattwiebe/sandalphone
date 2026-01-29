# Claude Code Instructions for Levi

## Python Environment Management

This project uses **uv** for Python environment and dependency management.

### CRITICAL: Always use uv commands

**NEVER:**
- `python script.py` ❌
- `pip install package` ❌

**ALWAYS:**
- `uv run python script.py` ✅
- `uv add package` ✅
- `uv sync` ✅

### Common Commands

**Run Mac backend:**
```bash
uv run --extra mac python mac/src/main.py
```

**Run Telegram bot:**
```bash
uv run --extra cloud python cloud/src/telegram_bot.py
```

**Add dependencies:**
```bash
# Mac-specific
uv add --optional mac "fastapi>=0.115.0"

# Cloud-specific
uv add --optional cloud "python-telegram-bot>=21.0"

# Shared
uv add "websockets>=12.0"
```

**Install dependencies:**
```bash
uv sync --extra mac      # Mac backend
uv sync --extra cloud    # Cloud bot
uv sync --all-extras     # Everything
```
