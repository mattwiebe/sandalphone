# DeepL API Setup (Recommended Alternative)

Since NLLB installation is problematic, **DeepL API is the fastest path forward**.

## Why DeepL?

- ✅ **No installation issues** - just add API key
- ✅ **Zero memory usage** - cloud API
- ✅ **Best translation quality** - often better than local models
- ✅ **Fast** - 150-300ms latency
- ✅ **Free tier** - 500k characters/month (plenty for voice messages)
- ✅ **No hallucinations** - professional translation service

## Quick Setup (2 minutes)

### 1. Get Free API Key

Visit: https://www.deepl.com/pro-api

- Sign up for free account
- Get API key from dashboard
- Free tier: 500,000 characters/month

### 2. Add to LaunchAgent

Edit the mac-backend plist:
```bash
nano ~/Library/LaunchAgents/com.levi.mac-backend.plist
```

Add these environment variables:
```xml
<key>EnvironmentVariables</key>
<dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin</string>
    <key>TRANSLATION_PROVIDER</key>
    <string>deepl</string>
    <key>DEEPL_API_KEY</key>
    <string>YOUR-API-KEY-HERE</string>
</dict>
```

### 3. Install requests library

```bash
uv add --optional mac requests
```

### 4. Restart service

```bash
./scripts/manage-services.sh restart
```

### 5. Test

Send a voice message to your Telegram bot!

## Testing Standalone

```bash
# Set API key
export DEEPL_API_KEY='your-key-here'

# Test DeepL client
uv run --extra mac python mac/src/llm/deepl_translation_client.py
```

Expected output:
```
✓ DeepL API client initialized (cloud-based, no local memory)

Test 1: Short Spanish → English
ES: ¿Cuál es tu mejor precio?
EN: What is your best price?

Test 3: Simple greeting
ES: Hola, ¿cómo estás?
EN: Hello, how are you?

✓ All tests complete!
```

## Memory Comparison

| Provider | Memory | Quality | Speed | Cost |
|----------|--------|---------|-------|------|
| Qwen-14B | 10-12GB | Good | Fast | Free |
| NLLB-600M | 1-2GB | Excellent | Fast | Free |
| **DeepL API** | **0GB** | **Best** | **Very Fast** | **Free tier** |

**With DeepL, total memory drops from 20GB → 10GB** (removing Qwen entirely)

## Usage Estimate

Voice messages are typically 5-30 seconds, ~50-200 characters transcribed.

**Free tier allowance:**
- 500,000 characters/month
- ÷ 100 chars/message average
- = **5,000 voice messages/month**
- = **~167 messages/day**

More than enough for personal use!

## Comparison with NLLB

| Feature | NLLB | DeepL |
|---------|------|-------|
| Setup | Complex (PyTorch issues) | Simple (API key) |
| Memory | 1-2GB | 0GB |
| Quality | Excellent | Best |
| Speed | Fast | Very Fast |
| Cost | Free | Free (500k chars/month) |
| Maintenance | Updates, model management | None |

**Recommendation: Start with DeepL**, test NLLB later when you have time to debug the installation.

## Reverting to Qwen

If you need to switch back:

```bash
# Edit plist, change:
<key>TRANSLATION_PROVIDER</key>
<string>qwen</string>

# Restart
./scripts/manage-services.sh restart
```

## Next Steps

After switching to DeepL:

1. ✅ Services use 10GB less memory (down to ~10GB total)
2. ✅ Translation quality improves (no more hallucinations)
3. ✅ Latency improves (150-300ms vs 2-4s)
4. ✅ No more installation/dependency issues

Then you can try NLLB later as a local alternative if you want to avoid API calls.
