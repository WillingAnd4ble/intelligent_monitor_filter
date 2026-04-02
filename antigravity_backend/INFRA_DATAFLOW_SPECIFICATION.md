# Infrastructure & Data Flow Specification
**Project:** Agent-based Information System for Personalized arXiv Publication Monitoring

## 1. Deployment & Infrastructure Components

### 1.1 Task Orchestration (Celery + Redis)
- **Broker & Results Backend:** `Redis`
- **Workers:** Distributed `Celery` workers capable of mapping async API batches.
- **Scheduler:** `Celery Beat` queries DB `notification_time` mapped parameters executing crons dynamically.

### 1.2 Model Hosting (`SPECTER2`)
SPECTER2 vectors map to 768-dims.
- **Location:** Huggingface `sentence-transformers` instantiated per Celery Worker entirely separating Web UI logic. 

### 1.3 Lexical Search Technology
- **Execution:** Firmly utilizing Native Postgres `tsvector` + `ts_rank` functionalities fused via standard RRF techniques to pgvector scores directly in python/SQL layers.

---

## 2. End-to-End Sequence Diagram

```mermaid
sequenceDiagram
    participant UI as Next.js Web UI
    participant API as FastAPI Backend
    participant Celery as Celery/Redis
    participant DB as Postgres (native tsvector)
    participant ArXiv as arXiv API
    participant LLM as External LLM / Modal.com Compute

    %% Initialization & Standalone Prep
    UI->>API: POST /api/v1/pipeline/trigger
    API->>Celery: async dispatch `run_discovery`
    API-->>UI: 202 Accepted, polls status polling loop

    Note over Celery,DB: Fetch Standalone Pre-req Contexts
    Celery->>DB: Fetch cached 'distilled_criteria' & 'feedback_memory'
    Celery->>Celery: SPECTER2 Embed (user_intent) ONLY ONCE

    %% Scraping & Embeddings
    Celery->>ArXiv: Fetch publications (delay 3.1s rate bounds)
    ArXiv-->>Celery: XML Papers payload
    Celery->>Celery: SPECTER2 Generate Embeddings
    Celery->>DB: UPSERT vectors

    %% Hybrid Search Funnel
    Note right of DB: Reciprocal Rank Fusion: ts_rank + cosine similarity vectors
    Celery->>DB: Query Top 50 Context candidates
    DB-->>Celery: 50 Narrowed Papers

    %% Fast Evaluation Stage
    Celery->>Celery: Run 50 Eval queries via asyncio.gather() Batch
    loop Over 50 Candidate Abstracts (Batched Parallel)
        Celery->>LLM: Evaluator
        LLM-->>Celery: EvaluatorOutput 
    end

    %% Deep Evaluation Stage
    loop Over passed candidates ONLY (EvaluatorOutput == accept|borderline)
        alt EvaluatorOutput == borderline
            Celery->>LLM: Critique
            LLM-->>Celery: True/False
        end

        alt EvaluatorOutput == accept OR CritiqueOutput == True
            Note over Celery,LLM: Deep Agent Scan Phase
            Celery->>LLM: PDFExtractor (Fetch PDF / Marker on Modal.com)
            Celery->>LLM: SectionClassifier
            Celery->>LLM: Explainer
            Celery->>LLM: Ranker
            Celery->>DB: INSERT user_papers (status='feed')
        end
    end

    %% End Process
    Celery-->>UI: State = COMPLETED
```

---

## 3. Environment Variables (.env)
A strictly documented `.env` configuration file framework required for a seamless deployment instance:

```env
# Application Core (FastAPI)
ENVIRONMENT=production # Enum: [local, staging, production]
JWT_SECRET=super_secret_cryptographically_secure_string_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=43200 # 30 Days sliding window

# Database & Broker Connectivity
DATABASE_URL=postgresql+asyncpg://postgres:password@db.supabase.co:5432/postgres
REDIS_URL=redis://localhost:6379/0

# External AI Compute
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-... # Fallback context LLM
MODAL_TOKEN_ID=ak-... 
MODAL_TOKEN_SECRET=as-...

# Sub-System Notifiers
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=bot@arxiv-intelligence-system.com
SMTP_PASSWORD=...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T...
```

---

## 4. Notification Dispatch Payloads

### 4.1 Daily Digest Email Template
**Subject Block:** `[arXiv Intelligence] 📚 Today's Top 5 Curated Papers`
**Body Render (HTML):**
```html
<h2>Here are your curated priority recommendations for today:</h2>

<!-- Iterated Dynamic Loop mapping the UI URL -->
<div class="paper-card">
  <h3><a href="{app_url}/library/{user_paper_id}">{title}</a></h3>
  <p><strong>Authors:</strong> {authors}</p>
  <p><strong>Agent's Take:</strong> {agent_explanation}</p>
  <p><em>Relevancy Score: {agent_score}/10</em></p>
  <hr />
</div>

<p><small>You are receiving this because your daily alert trigger is configured.</small></p>
```

### 4.2 Slack Block Kit Structure
```json
{
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text", 
        "text": "📚 Your Agent found new arXiv Picks!"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn", 
        "text": "*< {app_url}/library/{user_paper_id} | {title} >*\n_{authors}_\n> {agent_explanation}"
      }
    }
  ]
}
```
