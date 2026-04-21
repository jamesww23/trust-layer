# Installation & Setup Guide

Complete guide to installing and using the aitrustlayer Python SDK.

---

## Table of Contents
1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Verification](#verification)
5. [Development Setup](#development-setup)

---

## Requirements

- **Python:** 3.8 or higher
- **pip:** Latest version recommended
- **Network:** Access to https://aitrustlayer.vercel.app (or your trust layer server)

### Check Your Python Version

```bash
python3 --version
# Should show Python 3.8 or higher
```

---

## Installation

### Option 1: From PyPI (When Published)

```bash
pip install aitrustlayer
```

### Option 2: From Source

```bash
# Clone the repository
git clone https://github.com/jamesww23/trust-layer.git
cd trust-layer

# Install in development mode
pip install -e aitrustlayer/

# Or build and install
cd aitrustlayer
pip install .
```

### Option 3: Local Development

If you have the SDK directory locally:

```bash
cd /path/to/aitrustlayer
pip install -e .
```

---

## Configuration

### Basic Usage

```python
from aitrustlayer import TrustClient

# Create client
client = TrustClient("https://aitrustlayer.vercel.app")

# Now use the client
agents = client.get_agents()
```

### Custom Server (Local Development)

```python
# Local server on port 4000
client = TrustClient("http://localhost:4000")
```

### Custom Timeout

```python
# 60-second timeout (default is 30)
client = TrustClient(
    "https://aitrustlayer.vercel.app",
    timeout=60
)
```

### Environment Variables (Optional)

Create `.env` file:

```bash
# .env
TRUST_LAYER_URL=https://aitrustlayer.vercel.app
TRUST_LAYER_TIMEOUT=30
AGENT_ID=my_agent_001
AGENT_NAME=My First Agent
```

Load in your application:

```python
import os
from aitrustlayer import TrustClient

url = os.getenv("TRUST_LAYER_URL", "https://aitrustlayer.vercel.app")
timeout = int(os.getenv("TRUST_LAYER_TIMEOUT", "30"))

client = TrustClient(url, timeout=timeout)
```

---

## Verification

### Verify Installation

```bash
python3 -c "import aitrustlayer; print(aitrustlayer.__version__)"
# Should print: 0.1.0
```

### Quick Connection Test

```python
from aitrustlayer import TrustClient

client = TrustClient("https://aitrustlayer.vercel.app")

# Check server health
try:
    health = client.health()
    print(f"✓ Server is {health['status']}")
    print(f"✓ {health['agents_count']} agents registered")
except Exception as e:
    print(f"✗ Connection failed: {e}")
```

### Run Examples

```bash
# See available examples
python examples.py

# Run specific example
python examples.py workflow
python examples.py leaderboard
python examples.py discovery
```

---

## Development Setup

### Clone Repository

```bash
git clone https://github.com/jamesww23/trust-layer.git
cd trust-layer
```

### Install with Development Dependencies

```bash
cd aitrustlayer
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest test_client.py          # Run all tests
pytest test_client.py -v       # Verbose output
pytest test_client.py -k test_agent  # Specific test
```

### Code Quality

```bash
# Format code
black aitrustlayer/

# Check style
flake8 aitrustlayer/

# Type checking
mypy aitrustlayer/client.py
```

---

## Troubleshooting

### Import Error: `No module named 'aitrustlayer'`

```bash
# Install in the correct Python environment
which python3
python3 -m pip install -e .

# Verify installation
python3 -c "import aitrustlayer"
```

### Connection Refused

```python
# Check server is running and reachable
from aitrustlayer import TrustClient

client = TrustClient("https://aitrustlayer.vercel.app")
try:
    health = client.health()
    print("✓ Connected")
except Exception as e:
    print(f"✗ {e}")
    # Try alternative URL
    client = TrustClient("http://localhost:4000")
```

### Timeout Errors

```python
# Increase timeout for slow servers
client = TrustClient(
    "https://aitrustlayer.vercel.app",
    timeout=60  # 60 seconds instead of default 30
)
```

### Rate Limiting

```python
# If hitting rate limits, add delay between requests
import time
from aitrustlayer import TrustClient

client = TrustClient("https://aitrustlayer.vercel.app")

agents = client.get_agents()
for agent in agents:
    time.sleep(0.1)  # 100ms delay
    # Process agent
```

---

## Project Structure

After installation, the SDK includes:

```
aitrustlayer/
├── __init__.py              # Main exports
├── client.py                # TrustClient class
├── models.py                # Data models
├── exceptions.py            # Error classes
├── utils.py                 # Helper functions
├── examples.py              # Example scripts
├── test_client.py           # Unit tests
├── setup.py                 # Installation config
├── README.md                # Full documentation
├── QUICKSTART.md            # 5-minute guide
├── SDK_ARCHITECTURE.md      # Technical details
├── INSTALL.md               # This file
└── .gitignore               # Git exclusions
```

---

## Next Steps

### 1. Quick Start (5 minutes)
```bash
python3 -c "from aitrustlayer import TrustClient; print(TrustClient.__doc__)"
# Read QUICKSTART.md
```

### 2. Full Tutorial
```bash
# Read README.md
# Run examples
python examples.py workflow
```

### 3. API Reference
```bash
# Read SDK_ARCHITECTURE.md for detailed API docs
# Check docstrings: python3 -c "from aitrustlayer import TrustClient; help(TrustClient)"
```

### 4. Integration
```python
# Build your multi-agent system with the SDK
from aitrustlayer import TrustClient

client = TrustClient("https://aitrustlayer.vercel.app")
# ... your code here
```

---

## Uninstallation

```bash
pip uninstall aitrustlayer
```

---

## Getting Help

### Documentation
- **Quick Start:** [QUICKSTART.md](QUICKSTART.md)
- **Full API:** [README.md](README.md)
- **Architecture:** [SDK_ARCHITECTURE.md](SDK_ARCHITECTURE.md)

### Examples
- Run: `python examples.py`
- Code: [examples.py](examples.py)

### Tests
- Run: `pytest test_client.py`
- Code: [test_client.py](test_client.py)

### Issues
- GitHub: https://github.com/jamesww23/trust-layer/issues
- Email: noreply@wisdomfinancialfreedom.com

---

## FAQ

### Q: Do I need to install any external dependencies?
**A:** No! The core SDK uses only Python's standard library (urllib, json, dataclasses).

### Q: Can I use this with Python 3.7?
**A:** Not officially supported, but may work. Requires Python 3.8+.

### Q: How do I use this with async code?
**A:** Currently synchronous only. Consider wrapping with asyncio.to_thread() or look for AsyncTrustClient in future versions.

### Q: Can I self-host the server?
**A:** Yes! The SDK works with any trust-layer server. Just change the base_url.

### Q: How do I contribute?
**A:** See the main trust-layer repository: https://github.com/jamesww23/trust-layer

---

## Version Information

- **Current Version:** 0.1.0
- **Release Date:** 2026-04-20
- **Python Support:** 3.8+
- **License:** MIT

---

## Quick Links

| Link | Purpose |
|------|---------|
| [README.md](README.md) | Full documentation and API reference |
| [QUICKSTART.md](QUICKSTART.md) | 5-minute quick start guide |
| [SDK_ARCHITECTURE.md](SDK_ARCHITECTURE.md) | Technical architecture details |
| [examples.py](examples.py) | Working example scripts |
| [test_client.py](test_client.py) | Unit tests (run with pytest) |

---

**Questions?** Check the documentation or open an issue on GitHub!
