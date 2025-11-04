# otter

otter - Alpha Berkeley Agent Application

## Quick Start

```bash
# API keys were automatically configured from your environment
# Start services
framework deploy up

# Run CLI interface
framework chat
```

## Project Structure

```
otter/
├── otter/        # Application code
│   ├── registry.py
│   ├── capabilities/
│   └── context_classes.py
├── services/                  # Docker services
├── config.yml                 # Configuration
└── pyproject.toml            # Dependencies
```

## Development

Edit files in `otter/` to add functionality. Changes are reflected immediately.

## Documentation

- Framework: https://thellert.github.io/alpha_berkeley
- Tutorial: [Building Your First Capability](https://thellert.github.io/alpha_berkeley/developer-guides/building-first-capability.html)

