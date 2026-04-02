# Database Specification
**Project:** Agent-based Information System for Personalized arXiv Publication Monitoring

This document details the exact SQL/ORM schemas required to power the system utilizing **PostgreSQL** (optimally Supabase) and the specific extensions for semantic search and lexical ranking. 

*Assuming Python `SQLAlchemy` as the ORM mapper.*

---

## 1. Database Extensions
Before running migrations, the DB must enable the necessary extensions:
```sql
-- Semantic Search
CREATE EXTENSION IF NOT EXISTS vector;

-- Optional: ParadeDB BM25 extension for accurate Okapi BM25 scoring.
-- CREATE EXTENSION IF NOT EXISTS pg_search; 
```
*Note: If `pg_search` (ParadeDB) is not available on the managed host, lexical search will fall back to PostgreSQL's native document ranking (`tsvector` and `ts_rank`). Reciprocal Rank Fusion (RRF) will combine `ts_rank` and `cosine similarity` manually.*

---

## 2. Table Definitions & SQLAlchemy Models

### 2.1 Users Table
Stores authentication credentials.
```python
class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    settings = relationship("UserSettings", back_populates="user", uselist=False)
    papers = relationship("UserPaper", back_populates="user")
    feedback_memory = relationship("FeedbackMemory", back_populates="user", uselist=False)
```

### 2.2 User Settings Table
Houses all filtering intents and UI configurations.
```python
class UserSettings(Base):
    __tablename__ = 'user_settings'

    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    filtering_goal = Column(Text, nullable=True) 
    categories = Column(JSONB, default=["cs.AI"])
    topics = Column(JSONB, default=[]) 
    authors = Column(JSONB, default=[]) 
    content_interest = Column(JSONB, default=["introduction", "conclusions"])
    pdf_parser_mode = Column(String, default="pypdfium") 
    library_explanation_level = Column(String, default="professional") 
    notification_time = Column(String, default="09:00") 
    notification_channel = Column(String, default="email")

    user = relationship("User", back_populates="settings")
```

### 2.3 Papers Table
The global repository of scraped arXiv papers.
```python
class Paper(Base):
    __tablename__ = 'papers'

    id = Column(String, primary_key=True) # arxiv_id e.g., '2401.12345'
    title = Column(String, nullable=False)
    authors = Column(JSONB, nullable=False) 
    abstract = Column(Text, nullable=False)
    pdf_url = Column(String, nullable=False)
    source_url = Column(String, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False)

    embedding = Column(Vector(768)) 
```

### 2.4 Paper Categories Table
Links papers to their respective arXiv macro categories to enable fast declarative DB filtering before the vector funnel begins.
```python
class PaperCategory(Base):
    __tablename__ = 'paper_categories'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id = Column(String, ForeignKey('papers.id', ondelete='CASCADE'), index=True)
    category = Column(String, index=True, nullable=False) # e.g., 'cs.AI'
```

### 2.5 UserPapers Table
The many-to-many relationship mapping *which user* got *which paper*.
```python
class UserPaper(Base):
    __tablename__ = 'user_papers'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    paper_id = Column(String, ForeignKey('papers.id', ondelete='CASCADE'), nullable=False)
    
    status = Column(String, default="feed") # ENUM: feed, accepted, rejected
    agent_score = Column(Float, nullable=True) 
    agent_explanation = Column(Text, nullable=True) # Pipeline evaluation reason
    user_comment = Column(Text, nullable=True) # Reason user thumbs-downed it
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', 'paper_id', name='_user_paper_uc'),
        Index('ix_user_papers_user_status', 'user_id', 'status') # Optimization for dashboard lookups
    )
    
    user = relationship("User", back_populates="papers")
```

### 2.6 Paper Explanations Table
Stores lazy-cached library explanations. Calculated based on user demands from the library view.
```python
class PaperExplanation(Base):
    __tablename__ = 'paper_explanations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_paper_id = Column(UUID(as_uuid=True), ForeignKey('user_papers.id', ondelete='CASCADE'), index=True)
    explanation_level = Column(String, nullable=False) # professional | student | kid
    explanation_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('user_paper_id', 'explanation_level', name='_up_level_uc'),
    )
```

### 2.7 Feedback Memory Table
Stores the semantic memory characterizing user's rejections.
```python
class FeedbackMemory(Base):
    __tablename__ = 'feedback_memory'

    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    rejection_count = Column(Integer, default=0) # Controls logic to trigger LangGraph summarizer (e.g., sum on every 5 limits)
    summarized_feedback = Column(Text, nullable=True) 
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

---

## 3. Query Interactions & Pipeline Flows

### 3.1 Initial Pipeline Funnel (Lexical/Semantic Search)
To find the Top 50 candidates, combining Full-Text Search and Vector Similarity (RRF):
```sql
WITH paper_category_filter AS (
  SELECT p.id, p.title, p.abstract, p.embedding
  FROM papers p
  JOIN paper_categories pc ON p.id = pc.paper_id
  WHERE pc.category = ANY(ARRAY['cs.AI', 'cs.LG'])
),
text_search AS (
  SELECT id, ts_rank(to_tsvector('english', abstract), plainto_tsquery('english', '[user_goal]')) as txt_score
  FROM paper_category_filter
),
vector_search AS (
  SELECT id, (embedding <=> '[user_goal_vector]') as vec_score
  FROM paper_category_filter
)
-- Aggregate using RRF logic inside DB or SQLAlchemy to limit down to 50
```
