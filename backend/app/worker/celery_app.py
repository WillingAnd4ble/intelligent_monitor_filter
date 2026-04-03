import asyncio
import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from celery import Celery
from app.core.config import settings
from app.db.database import AsyncSessionLocal
from sqlalchemy import select

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
        async with AsyncSessionLocal() as session:
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

    asyncio.run(_run())


@celery_app.task(name="pipeline.trigger_goal_distiller")
def trigger_goal_distiller(user_id: str):
    """Hits the explicit GoalDistiller targeting custom properties."""
    from app.agents.distiller import run_goal_distiller
    from app.db.models import UserSettings
    import uuid
    
    async def _run():
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id)))
            settings_obj = result.scalars().first()
            if settings_obj:
                distilled = run_goal_distiller(
                    categories=settings_obj.categories,
                    topics=settings_obj.topics,
                    content_interest=settings_obj.content_interest,
                    filtering_goal=settings_obj.filtering_goal
                )
                settings_obj.distilled_criteria = distilled
                await session.commit()
                
    asyncio.run(_run())


@celery_app.task(name="pipeline.run_discovery")
def trigger_agent_discovery(user_id: str):
    """Entrypoint fetching local ArXiv boundaries mapping the RRF funnel strictly feeding LangGraph constraints organically."""
    from app.worker.arxiv_scraper import fetch_arxiv_papers, ingest_papers
    from app.db.retrieval import perform_hybrid_rrf_search
    from app.agents.graph import app as langgraph_app
    from app.db.models import UserSettings, UserPaper, Paper
    import uuid
    
    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.pool import NullPool
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        
        async with SessionLocal() as session:
            # 1. Pipeline Execution — fetch papers from user's configured categories
            result = await session.execute(select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id)))
            user_settings = result.scalars().first()
            categories = user_settings.categories if user_settings and user_settings.categories else ["cs.AI"]

            # Build ArXiv query from user categories (OR them together)
            cat_query = "+OR+".join(f"cat:{cat}" for cat in categories)
            papers = fetch_arxiv_papers(cat_query, max_results=200)
            await ingest_papers(session, papers)
            
            # 2. Validate user has distilled criteria before running pipeline
            if not user_settings or not user_settings.distilled_criteria:
                return

            # Load feedback memory for critique node
            from app.db.models import FeedbackMemory
            fm_result = await session.execute(
                select(FeedbackMemory).where(FeedbackMemory.user_id == uuid.UUID(user_id))
            )
            fm = fm_result.scalars().first()
            feedback_str = fm.summarized_feedback if fm and fm.summarized_feedback else ""

            # 3. Hybrid RRF Search mapping mock arrays locally
            mock_query_embed = [0.0] * 768
            candidates = await perform_hybrid_rrf_search(
                session=session,
                query_text=user_settings.filtering_goal or "AI Agents",
                query_embedding=mock_query_embed,
                limit=10,
                rrf_k=60
            )

            # 4. Standard Graph Nodes Engine Loop
            for cand in candidates:
                # Dedup: skip if UserPaper already exists for this (user, paper) pair
                existing_up = await session.execute(
                    select(UserPaper).where(
                        UserPaper.user_id == uuid.UUID(user_id),
                        UserPaper.paper_id == cand["id"]
                    )
                )
                if existing_up.scalars().first():
                    continue

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
                
                final_state = langgraph_app.invoke(state_input)
                
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
            
            await session.commit()

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

        await engine.dispose()

    asyncio.run(_run())

@celery_app.task(name="pipeline.trigger_memory_summarizer")
def run_memory_summarizer(user_id: str, new_comment: str):
    """Summarizes accumulated rejection comments into feedback_memory using Claude Haiku."""
    from app.db.models import FeedbackMemory
    from langchain_anthropic import ChatAnthropic
    from langchain_core.prompts import ChatPromptTemplate
    from app.agents.schemas import MemoryOutput
    import uuid

    async def _run():
        async with AsyncSessionLocal() as session:
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

            llm = ChatAnthropic(
                model="claude-3-haiku-20240307",
                temperature=0.0,
                api_key=settings.ANTHROPIC_API_KEY
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

    asyncio.run(_run())
