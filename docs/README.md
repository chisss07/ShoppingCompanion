# Shopping Companion - Architecture Documentation

**Version:** 1.0
**Date:** 2026-03-15
**Status:** Design Phase - Ready for Review

---

## Overview

Shopping Companion is an AI-powered Docker application that finds the best prices and in-stock items from reputable web sources. It features real-time multi-source price comparison, historical search tracking, AI-generated summaries, and alternative model recommendations.

## Core Features

1. **AI-Powered Search** - Natural language product search with intelligent query parsing
2. **Price Comparison** - Side-by-side comparison of 3+ sources per item with deal scoring
3. **Historical Searches** - Browsable history with price change tracking over time
4. **Alternative Models** - AI-identified newer/alternative products with spec comparisons
5. **Real-Time Updates** - WebSocket-driven progress showing which sources are being checked

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Backend API | Python 3.12 + FastAPI |
| AI/LLM | Anthropic Claude API (Sonnet) |
| Search Workers | Celery + gevent (async I/O) |
| Database | PostgreSQL 16 |
| Cache/Broker | Redis 7 |
| WebSocket | FastAPI WebSocket + Redis Pub/Sub |
| Scraping | httpx + BeautifulSoup4 + Playwright |
| Deployment | Docker Compose (8 services) |

## Architecture Documents

| Document | Description | Agent |
|----------|-------------|-------|
| [01-system-architecture.md](./01-system-architecture.md) | High-level system overview, AI pipeline, data flow, API design | AI Engineer |
| [02-architecture-patterns.md](./02-architecture-patterns.md) | Microservices patterns, CQRS, circuit breakers, security, scalability | Architect Reviewer |
| [03-ui-ux-design.md](./03-ui-ux-design.md) | Design system, wireframes, components, accessibility (WCAG 2.1 AA) | UI Designer |
| [04-websocket-architecture.md](./04-websocket-architecture.md) | Real-time events, rooms, Redis pub/sub, reconnection, scaling | WebSocket Engineer |
| [05-docker-deployment.md](./05-docker-deployment.md) | Docker Compose, Dockerfiles, networks, volumes, security hardening | Docker Expert |
| [06-database-architecture.md](./06-database-architecture.md) | PostgreSQL schema, indexes, partitioning, queries, Redis caching | Database Administrator |
| [07-performance-architecture.md](./07-performance-architecture.md) | SLOs, caching layers, load testing, scaling triggers, monitoring | Performance Engineer |
| [08-data-analytics-strategy.md](./08-data-analytics-strategy.md) | Data collection, price trends, quality framework, user analytics | Data Analyst |
| [09-dependency-management.md](./09-dependency-management.md) | Frontend/backend deps, version pinning, security scanning, updates | Dependency Manager |
| [10-search-strategy.md](./10-search-strategy.md) | Data sources, product matching, reputation scoring, freshness | Search Specialist |

## Service Architecture

```
                         +-------------------+
                         |   User (Browser)  |
                         +--------+----------+
                                  |
                         HTTP / WebSocket
                                  |
                    +-------------+-------------+
                    |     Nginx Reverse Proxy    |
                    +---+------------------+----+
                        |                  |
              +---------+------+   +-------+---------+
              | Frontend (React|   | WebSocket Server |
              | SPA - Nginx)   |   | (Python/FastAPI) |
              +----------------+   +---------+--------+
                                             |
                                   +---------+---------+
                                   | Backend API       |
                                   | (Python FastAPI)  |
                                   +--+------+------+--+
                                      |      |      |
                              +-------+  +---+---+  +--------+
                              |          |       |           |
                     +--------+--+ +-----+---+ +-+--------+ |
                     | PostgreSQL | |  Redis   | | Celery   | |
                     | Database   | |  Cache   | | Workers  | |
                     +------------+ +----------+ | (AI/Search)|
                                                 +-----+------+
                                                       |
                                            +----------+----------+
                                            | External APIs &     |
                                            | Web Sources         |
                                            +---------------------+
```

## Docker Services (8 containers)

| Service | Image | Purpose |
|---------|-------|---------|
| `nginx` | nginx:1.27-alpine | Reverse proxy, SSL, static files |
| `frontend` | node:22-alpine → nginx | React SPA |
| `backend` | python:3.13-slim | FastAPI REST API |
| `worker` | python:3.13-slim | Celery AI/Search workers |
| `websocket` | python:3.13-slim | WebSocket real-time server |
| `postgres` | postgres:16-alpine | Primary database |
| `redis` | redis:7-alpine | Cache + message broker |
| `playwright` | mcr.microsoft.com/playwright | Headless browser for JS scraping |

## External Data Sources

### Tier 1 - Official APIs
- Amazon Product Advertising API (PA-API 5.0)
- Best Buy Products API
- Walmart Affiliate API
- Google Shopping (via SerpAPI)
- eBay Browse API

### Tier 2 - Aggregators
- PriceGrabber API
- CamelCamelCamel (Amazon price history)

### Tier 3 - Web Scraping (fallback only)
- B&H Photo, Newegg, Target, Costco

## AI Pipeline (6 Stages)

```
User Query → [1] Query Understanding (Claude) → [2] Multi-Source Search (parallel APIs)
→ [3] Data Extraction & Normalization → [4] Price Comparison & Ranking
→ [5] Alternative Model Identification (Claude) → [6] Summary Generation (Claude)
```

## Getting Started

> **Note:** This documentation is in the design/review phase. No code has been written yet.
> Review all architecture documents before implementation begins.

## Repository

- **GitHub:** https://github.com/chisss07/ShoppingCompanion
