# Euronews Chatbot

An AI-powered chatbot that answers questions about EU policy, grounded in real European Commission documents updated daily.

Built with a Retrieval-Augmented Generation (RAG) pipeline: articles are scraped, chunked, embedded into a vector database, and retrieved at query time to ground LLM responses in real source documents.

## Features

- Daily automated scraping of EU Commission news articles (03:00)
- Semantic vector search via PostgreSQL + pgvector
- Small-to-big retrieval — chunks find documents, full content sent to the LLM
- Token-by-token streaming responses via SSE
- Source documents displayed with highlighted passages after every answer
- Conversation memory (last 10 messages)
- 7 open-weight LLM models switchable mid-conversation
- Dark / light mode UI

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + asyncio |
| Database | PostgreSQL 17 + pgvector |
| ORM | SQLAlchemy (async) + asyncpg |
| Embeddings | `all-MiniLM-L6-v2` via HuggingFace (local) |
| LLM Inference | HuggingFace Inference API via LangChain |
| Scraping | httpx + BeautifulSoup4 (lxml) |
| Scheduler | APScheduler (AsyncIOScheduler) |
| Frontend | Tailwind CSS + Vanilla JS (marked.js, highlight.js) |
| Containers | Docker Compose |

## Supported Models

| Model | Provider | Parameters |
|---|---|---|
| Llama 4 Scout *(default)* | Meta | 17B — 16 experts |
| Llama 4 Maverick | Meta | 17B — 128 experts |
| Qwen 3 235B | Alibaba | 235B — 22B active |
| Qwen 3 32B | Alibaba | 32B |
| DeepSeek V3 | DeepSeek | 671B — 37B active |
| Gemma 3 27B | Google | 27B |
| Llama 3.3 70B | Meta | 70B |

## Getting Started

### Prerequisites

- Docker and Docker Compose
- A [HuggingFace](https://huggingface.co) account with an API token

### Setup

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd text-analysis
   ```

2. Create a `.env` file:

   ```env
   HF_API_TOKEN=your_huggingface_token_here
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/text_analysis
   ```

3. Start the application:

   ```bash
   docker compose up --build
   ```

4. Open [http://localhost:8000](http://localhost:8000) in your browser.

The data pipeline runs automatically on startup and every day at 03:00, scraping and indexing the latest EU Commission articles.

## Project Structure

```
src/
├── modules/
│   ├── scraper/                 # Crawls EU Commission news pages
│   ├── preprocessor/            # Cleans, normalises, chunks articles
│   ├── embedder/                # Generates 384-dim vectors (all-MiniLM-L6-v2)
│   ├── persistence/             # PostgreSQL + pgvector storage and search
│   ├── data_collector_pipeline/ # Orchestrates scraper → preprocessor → embedder
│   ├── inference/               # RAG retrieval + LLM streaming
│   └── conversation/            # Conversation and message CRUD
├── config/                      # Settings and database connection
├── static/                      # Frontend (index.html, presentation.html)
└── main.py                      # FastAPI app entry point
```

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/conversation` | Create a new conversation |
| `GET` | `/api/conversation` | List all conversations |
| `GET` | `/api/conversation/{id}` | Get conversation with messages |
| `DELETE` | `/api/conversation/{id}` | Delete a conversation |
| `POST` | `/api/inference/chat` | Send a message (SSE streaming) |
| `GET` | `/api/inference/models` | List available models |
| `GET` | `/health` | Health check |
| `GET` | `/presentation` | View project presentation |

## License

Licensed under the [Apache License 2.0](LICENSE).
