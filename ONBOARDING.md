# Quick Onboarding Checklist

Welcome! This is a quick checklist to get you started. For detailed information, see the documentation links below.

## ✅ Initial Setup

- [ ] Dependencies installed: `uv pip install -e .`
- [ ] `.env` file created: `cp .env.example .env`
- [ ] Things 3 authentication token configured: `python scripts/configure_token.py`
  - Get token from: Things 3 → Settings → General → Enable Things URLs

## 🚀 Quick Test

```bash
# Start server
uv run dev

# Verify it works (in another terminal)
curl http://127.0.0.1:8009/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## 📚 Documentation

- **[README.md](README.md)** - Project overview, quick start, and GTD tools
- **[docs/DEVELOPERS.md](docs/DEVELOPERS.md)** - Complete developer guide (setup, architecture, testing, contributing)
- **[CLAUDE.md](CLAUDE.md)** - Quick reference for AI assistants
- **[docs/TESTING.md](docs/TESTING.md)** - Testing guide

## 🎯 Next Steps

1. Read [README.md](README.md) for project overview
2. Review [docs/DEVELOPERS.md](docs/DEVELOPERS.md) for development workflow
3. Run tests: `uv run python -m pytest tests`
4. Explore the code: `src/things_mcp/fast_server.py`

---

**That's it!** All the details are in the documentation above. 🚢
