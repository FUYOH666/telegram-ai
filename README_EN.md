# Telegram AI Assistant Platform

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![uv](https://img.shields.io/badge/uv-managed-orange.svg)](https://github.com/astral-sh/uv)

**🇬🇧 [English version](README_EN.md) | 🇷🇺 [Русская версия](README.md)**

A platform for connecting artificial intelligence to personal Telegram accounts with capabilities for managing, monitoring, and analyzing conversations and voice messages.

The platform allows you to connect AI to your personal Telegram account for automatic message processing, dialogue analysis, data extraction, meeting management, and much more. Suitable for both research projects (analyzing your own messages through local vLLM/ASR) and commercial applications (AI assistants for business, communication automation).

💬 **Want to try it in action?** Chat with a live example bot: [@ScanovichAI](https://t.me/ScanovichAI) on Telegram!

## ✨ Key Features

### Connecting AI to Personal Account
- 🤖 **AI Assistant** for your personal Telegram account with support for vLLM and OpenAI-compatible API
- 🎤 **Voice message processing** with automatic transcription via ASR
- 📊 **Conversation analytics** - automatic data extraction with confidence scores
- 🔍 **Dialogue monitoring** - tracking and analysis of all incoming messages

### Management and Automation
- 📅 **Google Calendar integration** for automatic meeting management
- 🎯 **Sales Flow** with lead qualification through fit-score system
- 🔔 **Event system** for flexible management and automation
- 📡 **REST API** for integrations with external systems (CRM, analytics)

### Intelligent Capabilities
- 🧠 **RAG system** for searching company knowledge base
- 💾 **Context memory** - storage and analysis of dialogue history
- 📈 **Automatic summarization** of long conversations
- 🔗 **Web link parsing** - automatic extraction and analysis of web page content from messages
- ✅ **Consent management** (PDPA/GDPR) for compliance

## Architecture

The project is organized as a microservices architecture:

```
telegram-ai-platform/
├── services/                    # Microservices
│   ├── telegram-bot/            # Telegram bot service
│   ├── api-gateway/             # REST API Gateway
│   ├── analytics/               # Analytics service
│   └── worker/                  # Celery workers
├── shared/                      # Shared modules
│   ├── database/                # SQLAlchemy models, migrations
│   ├── cache/                   # Redis clients
│   ├── events/                  # Event schemas
│   ├── config/                  # Configuration
│   └── utils/                   # Utilities
├── infrastructure/              # Infrastructure
│   ├── docker-compose.yml       # Local development
│   └── kubernetes/             # K8s manifests (optional)
├── scripts/                     # Utilities
└── tests/                       # Tests
```

## Technology Stack

- **Python 3.12+** - main language
- **FastAPI** - REST API
- **LangChain + LangGraph** - chains and agents
- **PostgreSQL 16** - main database (with SQLite support for backward compatibility)
- **Redis 7** - caching and queues
- **Celery** - asynchronous tasks
- **Telethon** - Telegram API client
- **ChromaDB** - vector storage for RAG

## Use Cases

### Connecting AI to Personal Account
- **Management**: Automatic processing of incoming messages, answering questions, meeting management
- **Monitoring**: Tracking all dialogues, activity analysis, communication control
- **Analytics**: Data extraction from conversations, voice message analysis, dialogue statistics

### Research Use
- Analyzing your own messages through local vLLM server
- Experiments with various LLM models for processing personal data
- Exploring Speech-to-Text (ASR) capabilities for voice message transcription
- Testing RAG systems on your own data
- Developing and testing AI agents on real dialogues

### Commercial Applications
- AI assistants for business with automatic data extraction from dialogues
- Integration with CRM systems via REST API for data synchronization
- Meeting management through Google Calendar with automatic slot suggestions
- Lead qualification using fit-score system
- Voice message processing for customer support
- Communication analytics for business intelligence

## Code Quality and Security

The project follows Python development best practices:

- ✅ **Linting and formatting**: Ruff for code linting and formatting
- ✅ **Type checking**: Pyright for static type checking
- ✅ **Code security**: Bandit for finding vulnerabilities in code
- ✅ **Spell checking**: Codespell for spell checking
- ✅ **Dependency audit**: pip-audit for checking vulnerabilities in dependencies
- ✅ **Pre-commit hooks**: Automatic checks before commit
- ✅ **CI/CD**: Automatic checks in GitHub Actions
- ✅ **Security scan**: Trivy for scanning Docker images and file system
- ✅ **Prometheus metrics**: `/metrics` endpoint for performance monitoring

### Setting up pre-commit hooks

After installing dependencies, activate pre-commit hooks:

```bash
uv sync
uv run pre-commit install
```

Now code checks will run automatically on each commit.

## New Features (v0.7.0)

### 🎯 Smart Data Extraction with Confidence
- Automatic confidence calculation (0.0-1.0) for each extracted slot
- Clarifying questions at low confidence (< 0.6)
- Soft confirmations at medium confidence (0.6-0.8)
- Usage without clarification at high confidence (≥ 0.8)

### 📊 Fit-score System for Lead Qualification
- Automatic fit_score calculation (0-100) based on collected information
- Threshold of 60 for meeting proposal (configurable)
- Detailed breakdown by components for analysis
- Integration into meeting decision process

### 🔔 Event System
- EventBus for publishing and subscribing to events
- Events: new messages, found slots, intent changes, time proposals, consents
- Hybrid approach: events + existing state machine

### 📅 Improved Meeting Management
- Tentative meeting bookings for 15 minutes with automatic cancellation
- Idempotency: preventing duplicate meetings
- Slot suggestions considering user timezone
- Mini agenda for meetings based on collected data

### ✅ Consent Management (PDPA)
- Automatic consent request when collecting contacts
- Consent request before creating meetings
- Consent storage with timestamp
- PDPA support for Thailand

## Project Status

✅ **Project is ready to use!** All components are tested and working.

See [DOCUMENTATION.md](DOCUMENTATION.md#статус-проекта) for detailed status of all components.

## 🚀 Quick Start

### Requirements

- Python 3.12
- uv (package manager)
- Docker and Docker Compose (for PostgreSQL and Redis, optional)
- AI server (vLLM or OpenAI-compatible API) - can use locally or cloud
- ASR server (optional, for voice message processing)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/FUYOH666/telegram-ai.git
cd telegram-ai
```

2. Install dependencies:
```bash
uv sync
```

3. Copy `.env.example` to `.env` and configure environment variables:
```bash
cp .env.example .env
```

Edit the `.env` file:
```env
# Telegram API credentials (get from https://my.telegram.org)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+7XXXXXXXXXX
TELEGRAM_SESSION_PATH=./sessions/your_bot.session

# AI Server (vLLM or OpenAI-compatible API)
# For local development: http://localhost:8000
# For production: http://100.93.82.48:8000
AI_SERVER_BASE_URL=http://100.93.82.48:8000
# API key optional if needed
AI_SERVER_API_KEY=

# ASR Server (for voice message transcription)
# For local development: http://localhost:8001
# For production: http://100.93.82.48:8001
ASR_SERVER_BASE_URL=http://100.93.82.48:8001

# Meeting Summary
MEETING_OWNER_USERNAME=@your_username

# Database (optional, SQLite by default)
# DATABASE_URL=postgresql://user:password@localhost:5432/telegram_ai

# Redis (optional)
# REDIS_URL=redis://localhost:6379/0
```

4. Start infrastructure:
```bash
docker-compose -f infrastructure/docker-compose.yml up -d
```

5. Run database migrations (if using PostgreSQL):
```bash
alembic upgrade head
```

6. Check configuration and server availability:
```bash
uv run python -m src.telegram_ai.main health
```

This command will check:
- ✅ Configuration and environment variables
- ✅ AI server availability (vLLM)
- ✅ ASR server availability
- ✅ Database
- ✅ RAG knowledge base
- ✅ Google Calendar credentials (if enabled)

7. Start Telegram Bot:
```bash
uv run python scripts/start_telegram_bot.py
```

On startup, AI server availability is automatically checked. If the server is unavailable, the application will not start with a clear error message.

8. Start API Gateway (in a separate terminal):
```bash
uv run python scripts/start_api_gateway.py
```

## Configuration

Main configuration is in `config.yaml`. Environment variables with prefixes are supported:

- `TELEGRAM_*` - Telegram settings
- `AI_SERVER_*` - vLLM server settings
- `ASR_SERVER_*` - ASR server settings
- `URL_PARSING_*` - URL parsing settings
- `DATABASE_*` - Database settings
- `REDIS_*` - Redis settings

## Server Configuration

The platform supports various deployment options:

- **Local servers**: Run vLLM and ASR servers locally (see documentation for respective projects)
- **Cloud servers**: Specify your server URLs in environment variables `AI_SERVER_BASE_URL` and `ASR_SERVER_BASE_URL`
- **OpenAI API**: Use OpenAI-compatible API by specifying the corresponding URL

All settings can be configured via environment variables or `config.yaml`.

### Checking Server Availability

On application startup, AI server availability is automatically checked. If the server is unavailable, the application will not start with a clear error message.

For manual check, use the command:
```bash
uv run python -m src.telegram_ai.main health
```

This command will check all system components and show their status.

## Development

### Service Structure

Each service has its own `pyproject.toml` and can be deployed independently.

### Adding New Endpoints to API Gateway

Create a file in `services/api-gateway/src/routes/` and connect the router in `main.py`.

### Adding New Celery Tasks

Create a file in `services/worker/src/tasks/` and register the task.

## 📚 Documentation

- **[DOCUMENTATION.md](DOCUMENTATION.md)** - Full technical documentation (project status, migration, rate limiting, testing)
- **[CHANGELOG.md](CHANGELOG.md)** - Project change history
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Guide for contributing to the project
- **[README.md](README.md)** - Russian version of README

## Main Components

### Sales Flow
- State machine: GREETING → NEEDS_DISCOVERY → PRESENTATION → CONSULTATION_OFFER → SCHEDULING
- Automatic slot extraction with confidence
- Fit-score for lead qualification
- Event system integration

### Memory
- Dialogue storage in SQLite/PostgreSQL
- Vector storage (ChromaDB) for RAG
- Automatic summarization of long dialogues
- Slot storage with confidence and metadata

### URL Parsing
- Automatic URL detection in user messages
- Web page content extraction
- Support for trafilatura and BeautifulSoup for reliable parsing
- Configurable limits on URL count and content size
- Integration with dialogue context for more accurate responses

### Calendar Integration
- Google Calendar API integration
- Tentative meeting bookings
- Meeting creation idempotency
- Slot suggestions considering timezone

### Consent Management
- Consent management (PDPA, GDPR)
- Automatic consent requests
- Consent storage with timestamp
- User response parsing

## Project Status

✅ **All components are tested and working:**
- Telegram Bot Service - starts and processes messages
- API Gateway - 8 REST endpoints working with real database
- Database - SQLite works, PostgreSQL ready for use
- AI integrations - connected to existing servers (vLLM, ASR)
- Voice messages - receiving and transcription working
- Text messages - fully functional

## Contributing

We welcome contributions to the project!

### How to Contribute

1. Fork the repository
2. Create a branch for your feature (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Rules

- Follow the project code style (ruff for formatting)
- Run pre-commit hooks before commit (`uv run pre-commit run --all-files`)
- Add tests for new features
- Update documentation as needed
- Use meaningful commit messages
- Check code for security (bandit) before commit

Please create Issues for bugs and suggestions!

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contacts

- **GitHub**: [@FUYOH666](https://github.com/FUYOH666)
- **Telegram**: [@ScanovichAI](https://t.me/ScanovichAI) - chat with a live example bot!
- **Email**: iamfuyoh@gmail.com

## Author

FUYOH666

