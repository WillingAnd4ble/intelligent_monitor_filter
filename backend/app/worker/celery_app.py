import asyncio
import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from celery import Celery
from app.core.config import settings
from sqlalchemy import select


def _run_async(coro):
    """Run an async coroutine from a sync Celery task without killing the worker.

    asyncio.run() aggressively cancels pending tasks and sets the event loop to
    None on exit.  With --pool=solo (main-thread execution), this destroys Modal
    SDK background coroutines and can cause the Celery worker process to exit.

    This helper creates a fresh loop, runs the coroutine, and closes the loop
    without nuking the thread-level event loop reference.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        except Exception:
            pass


celery_app = Celery(
    "arxiv_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "dispatch-pipelines-hourly": {
            "task": "pipeline.dispatch_scheduled_runs",
            "schedule": 3600,  # every hour
        },
    },
)

@celery_app.task(name="pipeline.dispatch_scheduled_runs")
def dispatch_scheduled_runs():
    """Hourly dispatcher: finds users whose notification_time matches the current UTC hour
    and enqueues a pipeline run for each."""
    from app.db.models import UserSettings
    from datetime import datetime, timezone
    import logging

    logger = logging.getLogger(__name__)
    current_hour = datetime.now(timezone.utc).strftime("%H:00")

    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.pool import NullPool
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        async with SessionLocal() as session:
            result = await session.execute(
                select(UserSettings).where(
                    UserSettings.notification_time == current_hour,
                    UserSettings.distilled_criteria.isnot(None),
                )
            )
            users = result.scalars().all()
            for us in users:
                user_id_str = str(us.user_id)
                logger.info(f"Scheduling pipeline run for user {user_id_str} (notification_time={current_hour})")
                trigger_agent_discovery.delay(user_id_str)
        await engine.dispose()

    _run_async(_run())


@celery_app.task(name="pipeline.trigger_goal_distiller")
def trigger_goal_distiller(user_id: str):
    """Distills filtering criteria AND embeds filtering_goal via SPECTER2."""
    from app.agents.distiller import run_goal_distiller
    from app.worker.modal_client import specter2_embed_batch
    from app.db.models import UserSettings
    import uuid

    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.pool import NullPool
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        async with SessionLocal() as session:
            result = await session.execute(select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id)))
            settings_obj = result.scalars().first()
            if settings_obj:
                # 1. Distill criteria (existing logic)
                distiller_output = run_goal_distiller(
                    categories=settings_obj.categories,
                    topics=settings_obj.topics,
                    content_interest=settings_obj.content_interest,
                    filtering_goal=settings_obj.filtering_goal
                )
                settings_obj.distilled_criteria = distiller_output.distilled_criteria
                settings_obj.lexical_query = distiller_output.lexical_query

                # 2. Embed filtering_goal via SPECTER2
                if settings_obj.filtering_goal:
                    embeddings = await specter2_embed_batch([
                        {"title": settings_obj.filtering_goal, "abstract": settings_obj.filtering_goal}
                    ])
                    settings_obj.goal_embedding = embeddings[0]

                await session.commit()
        await engine.dispose()

    _run_async(_run())


@celery_app.task(name="pipeline.run_discovery")
def trigger_agent_discovery(user_id: str):
    """Entrypoint fetching local ArXiv boundaries mapping the RRF funnel strictly feeding LangGraph constraints organically."""
    from app.worker.arxiv_scraper import fetch_arxiv_papers, ingest_papers
    from app.db.retrieval import perform_hybrid_rrf_search
    from app.agents.graph import app as langgraph_app
    from app.db.models import UserSettings, UserPaper, Paper
    import uuid
    import logging

    logger = logging.getLogger(__name__)

    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.pool import NullPool
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with SessionLocal() as session:
                # 1. Pipeline Execution — fetch papers from user's configured categories
                result = await session.execute(select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id)))
                user_settings = result.scalars().first()
                categories = user_settings.categories if user_settings and user_settings.categories else ["cs.AI"]

                # Build ArXiv query from user categories (OR them together)
                cat_query = "+OR+".join(f"cat:{cat}" for cat in categories)
                logger.info(f"[discovery:{user_id[:8]}] Fetching ArXiv papers for categories: {categories}")
                papers = fetch_arxiv_papers(cat_query, max_results=200)
                logger.info(f"[discovery:{user_id[:8]}] Fetched {len(papers)} papers from ArXiv, ingesting...")
                await ingest_papers(session, papers)
                logger.info(f"[discovery:{user_id[:8]}] Ingestion complete")

                # 2. Validate user has distilled criteria before running pipeline
                if not user_settings or not user_settings.distilled_criteria:
                    logger.warning(
                        f"[discovery:{user_id[:8]}] ABORTING — no distilled_criteria. "
                        f"user_settings exists: {user_settings is not None}, "
                        f"filtering_goal: {getattr(user_settings, 'filtering_goal', None)!r}"
                    )
                    return

                # Load feedback memory for critique node
                from app.db.models import FeedbackMemory
                fm_result = await session.execute(
                    select(FeedbackMemory).where(FeedbackMemory.user_id == uuid.UUID(user_id))
                )
                fm = fm_result.scalars().first()
                feedback_str = fm.summarized_feedback if fm and fm.summarized_feedback else ""

                # 3. Hybrid RRF Search with real SPECTER2 query embedding
                query_embedding = user_settings.goal_embedding
                if query_embedding is None:
                    # Fallback: embed on-the-fly if goal_embedding not cached yet
                    from app.worker.modal_client import specter2_embed_batch
                    if user_settings.filtering_goal:
                        logger.info(f"[discovery:{user_id[:8]}] goal_embedding missing, embedding on-the-fly")
                        embeddings = await specter2_embed_batch([
                            {"title": user_settings.filtering_goal, "abstract": user_settings.filtering_goal}
                        ])
                        query_embedding = embeddings[0]
                    else:
                        logger.warning(f"[discovery:{user_id[:8]}] No filtering_goal — using zero vector for semantic search")
                        query_embedding = [0.0] * 768

                logger.info(f"[discovery:{user_id[:8]}] Running hybrid RRF search...")
                candidates = await perform_hybrid_rrf_search(
                    session=session,
                    query_text=user_settings.lexical_query or user_settings.filtering_goal or "AI Agents",
                    query_embedding=query_embedding,
                    limit=20,
                )
                logger.info(f"[discovery:{user_id[:8]}] RRF returned {len(candidates)} candidates")

                # 4. Standard Graph Nodes Engine Loop
                evaluated_count = 0
                feed_count = 0
                for i, cand in enumerate(candidates):
                    # Dedup: skip if UserPaper already exists for this (user, paper) pair
                    existing_up = await session.execute(
                        select(UserPaper).where(
                            UserPaper.user_id == uuid.UUID(user_id),
                            UserPaper.paper_id == cand["id"]
                        )
                    )
                    if existing_up.scalars().first():
                        continue

                    try:
                        state_input = {
                            "user_id": user_id,
                            "user_intent": user_settings.filtering_goal or "General",
                            "distilled_criteria": user_settings.distilled_criteria,
                            "content_interest": user_settings.content_interest,
                            "feedback_memory": feedback_str,
                            "current_paper_id": cand["id"],
                            "raw_abstract": cand["abstract"],
                            "pdf_url": cand.get("pdf_url"),
                            "extracted_pdf_text": None,
                            "sectioned_text": None,
                            "evaluator_decision": "borderline",
                            "evaluator_reasonbook": "",
                            "critique_decision": True,
                            "critique_reasonbook": "",
                            "final_explanation": "",
                            "agent_score": 0.0
                        }

                        final_state = await langgraph_app.ainvoke(state_input)

                        # 'feed' = show in user feed for review, 'rejected' = agent filtered out
                        # 'accepted' is reserved for user explicit accept action
                        status_val = "rejected"
                        if final_state.get("evaluator_decision") == "reject" or final_state.get("critique_decision") is False:
                            status_val = "rejected"
                        elif final_state.get("evaluator_decision") in ("accept", "borderline"):
                            status_val = "feed"

                        new_up = UserPaper(
                            user_id=uuid.UUID(user_id),
                            paper_id=cand["id"],
                            status=status_val,
                            agent_score=final_state.get("agent_score"),
                            agent_explanation=final_state.get("final_explanation")
                        )
                        session.add(new_up)
                        evaluated_count += 1
                        if status_val == "feed":
                            feed_count += 1
                        logger.info(
                            f"[discovery:{user_id[:8]}] Paper {i+1}/{len(candidates)} "
                            f"'{cand['id']}' → {status_val} (score={final_state.get('agent_score')})"
                        )
                    except Exception as e:
                        logger.error(f"[discovery:{user_id[:8]}] LangGraph failed on paper '{cand['id']}': {e}", exc_info=True)
                        continue

                await session.commit()
                logger.info(f"[discovery:{user_id[:8]}] Pipeline complete — {evaluated_count} evaluated, {feed_count} recommended")

                # 5. Notify user about top-ranked papers (FR17-FR18)
                from app.worker.notifications import notify_top_picks, TOP_PICK_THRESHOLD
                from app.db.models import User
                top_papers_result = await session.execute(
                    select(UserPaper, Paper)
                    .join(Paper, UserPaper.paper_id == Paper.id)
                    .where(
                        UserPaper.user_id == uuid.UUID(user_id),
                        UserPaper.status == "feed",
                        UserPaper.agent_score >= TOP_PICK_THRESHOLD
                    )
                    .order_by(UserPaper.agent_score.desc())
                    .limit(10)
                )
                top_rows = top_papers_result.all()
                if top_rows:
                    user_result = await session.execute(
                        select(User).where(User.id == uuid.UUID(user_id))
                    )
                    user_obj = user_result.scalars().first()
                    top_papers_data = [
                        {
                            "title": paper.title,
                            "source_url": paper.source_url,
                            "agent_score": up.agent_score,
                            "agent_explanation": up.agent_explanation,
                        }
                        for up, paper in top_rows
                    ]
                    notify_top_picks(user_obj.email, top_papers_data)
        except Exception as e:
            logger.error(f"[discovery:{user_id[:8]}] TASK FAILED: {e}", exc_info=True)
            raise
        finally:
            await engine.dispose()
    _run_async(_run())

@celery_app.task(name="library.generate_deep_explanation")
def generate_deep_explanation(user_paper_id: str, user_id: str):
    """Generates a deep, PDF-based explanation for an accepted library paper.

    Steps: Marker PDF extraction -> section classification -> LLM deep explanation -> cache.
    """
    from app.worker.modal_client import marker_extract_pdf
    from app.agents.section_classifier import classify_sections
    from app.db.models import UserSettings, UserPaper, Paper, PaperExplanation
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from pydantic import BaseModel, Field
    import uuid
    import logging

    logger = logging.getLogger(__name__)

    class DeepExplanationOutput(BaseModel):
        explanation: str = Field(description="Markdown-formatted deep explanation, 300-600 words")

    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.pool import NullPool
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        async with SessionLocal() as session:
            # Load user_paper + paper
            result = await session.execute(
                select(UserPaper, Paper)
                .join(Paper, UserPaper.paper_id == Paper.id)
                .where(UserPaper.id == uuid.UUID(user_paper_id))
                .where(UserPaper.user_id == uuid.UUID(user_id))
            )
            row = result.first()
            if not row:
                logger.error(f"UserPaper {user_paper_id} not found for user {user_id}")
                return
            user_paper, paper = row

            # Load user settings
            settings_result = await session.execute(
                select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id))
            )
            user_settings = settings_result.scalars().first()
            level = user_settings.library_explanation_level if user_settings else "professional"
            content_interest = user_settings.content_interest if user_settings else []
            filtering_goal = user_settings.filtering_goal if user_settings else ""

            # Step 1: Fetch full PDF text via Marker
            extracted_text = await marker_extract_pdf(paper.pdf_url)
            if not extracted_text:
                extracted_text = paper.abstract

            # Step 2: Classify and filter sections
            filtered_text = classify_sections(extracted_text, content_interest or [])

            # Step 3: Generate deep explanation via LLM
            level_instructions = {
                "professional": (
                    "Write for an expert researcher. Use precise technical language, "
                    "discuss methodology, experimental design, implications, and limitations. "
                    "Assume domain knowledge."
                ),
                "student": (
                    "Write for a university student. Explain key concepts, define acronyms, "
                    "relate findings to the broader field, and walk through results step by step."
                ),
                "kid": (
                    "Write in plain language for a curious 12-year-old. Use analogies, "
                    "no jargon, and focus on what they did and why it matters."
                ),
            }

            llm = ChatOpenAI(
                model="gpt-5.4-nano-2026-03-17",
                temperature=0.7,
                api_key=settings.OPENAI_API_KEY,
            )
            structured = llm.with_structured_output(DeepExplanationOutput)

            authors_str = ", ".join(paper.authors) if paper.authors else "Unknown"

            prompt = ChatPromptTemplate.from_messages([
                ("system", (
                    "You are writing a deep explanation of a scientific paper for a user. "
                    "{level_instruction} "
                    "The user's research goal: {filtering_goal}\n\n"
                    "Write a 300-600 word markdown explanation with headers, bullets, and bold key terms. "
                    "This should be a deep read, not a 3-sentence summary."
                )),
                ("human", (
                    "Paper: {title}\n"
                    "Authors: {authors}\n\n"
                    "Relevant sections:\n{filtered_text}"
                )),
            ])

            chain = prompt | structured
            output = chain.invoke({
                "level_instruction": level_instructions.get(level, level_instructions["professional"]),
                "filtering_goal": filtering_goal or "General AI research",
                "title": paper.title,
                "authors": authors_str,
                "filtered_text": filtered_text,
            })

            # Step 4: Cache result (upsert to handle race condition)
            existing = await session.execute(
                select(PaperExplanation)
                .where(PaperExplanation.user_paper_id == uuid.UUID(user_paper_id))
                .where(PaperExplanation.level == level)
            )
            existing_row = existing.scalars().first()

            if existing_row:
                existing_row.explanation = output.explanation
            else:
                session.add(PaperExplanation(
                    user_paper_id=uuid.UUID(user_paper_id),
                    level=level,
                    explanation=output.explanation,
                ))

            await session.commit()
            logger.info(f"Deep explanation cached for user_paper {user_paper_id} at level '{level}'")
        await engine.dispose()

    _run_async(_run())


@celery_app.task(name="pipeline.trigger_memory_summarizer")
def run_memory_summarizer(user_id: str, new_comment: str):
    """Summarizes accumulated rejection comments into feedback_memory using Claude Haiku."""
    from app.db.models import FeedbackMemory
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from app.agents.schemas import MemoryOutput
    import uuid

    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.pool import NullPool
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        async with SessionLocal() as session:
            result = await session.execute(
                select(FeedbackMemory).where(FeedbackMemory.user_id == uuid.UUID(user_id))
            )
            memory = result.scalars().first()

            if not memory:
                memory = FeedbackMemory(
                    user_id=uuid.UUID(user_id),
                    summarized_feedback="",
                    rejection_count=0
                )
                session.add(memory)

            memory.rejection_count = (memory.rejection_count or 0) + 1
            existing_feedback = memory.summarized_feedback or ""

            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.0,
                api_key=settings.OPENAI_API_KEY
            )
            structured = llm.with_structured_output(MemoryOutput)

            prompt = ChatPromptTemplate.from_messages([
                ("system", (
                    "You maintain a concise summary of what a user dislikes in academic papers. "
                    "Merge the new rejection comment into the existing summary. "
                    "Keep the result under 300 words. Preserve all prior dislikes and add new ones."
                )),
                ("human", (
                    "Existing summary:\n{existing}\n\n"
                    "New rejection comment:\n{new_comment}\n\n"
                    "Output the updated consolidated summary."
                ))
            ])

            chain = prompt | structured
            result = chain.invoke({
                "existing": existing_feedback if existing_feedback else "No prior feedback.",
                "new_comment": new_comment
            })

            memory.summarized_feedback = result.summarized_feedback
            await session.commit()
        await engine.dispose()

    _run_async(_run())
