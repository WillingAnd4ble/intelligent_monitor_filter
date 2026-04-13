import asyncio
import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from celery import Celery
from app.core.config import settings
from sqlalchemy import select


def _run_async(coro):
    """Run an async coroutine from a sync Celery task.

    Creates a fresh loop to avoid destroying Modal SDK background coroutines
    when running with --pool=solo (main-thread execution).
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
            "schedule": 3600,
        },
    },
)


def _make_session():
    """Create a fresh async engine + sessionmaker (NullPool for Celery tasks)."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.pool import NullPool
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session_factory


# ─────────────────────────────────────────────────────────────────────
# Scheduler
# ─────────────────────────────────────────────────────────────────────

@celery_app.task(name="pipeline.dispatch_scheduled_runs")
def dispatch_scheduled_runs():
    """Hourly dispatcher: finds users whose notification_time matches current UTC hour."""
    from app.db.models import UserSettings
    from datetime import datetime, timezone
    import logging

    logger = logging.getLogger(__name__)
    current_hour = datetime.now(timezone.utc).strftime("%H:00")

    async def _run():
        engine, SessionLocal = _make_session()
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


# ─────────────────────────────────────────────────────────────────────
# Goal Distiller
# ─────────────────────────────────────────────────────────────────────

@celery_app.task(name="pipeline.trigger_goal_distiller")
def trigger_goal_distiller(user_id: str):
    """Distills filtering criteria + lexical_query AND embeds filtering_goal via SPECTER2."""
    from app.agents.distiller import run_goal_distiller
    from app.worker.modal_client import specter2_embed_batch
    from app.db.models import UserSettings
    import uuid

    async def _run():
        engine, SessionLocal = _make_session()
        async with SessionLocal() as session:
            result = await session.execute(select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id)))
            settings_obj = result.scalars().first()
            if settings_obj:
                distiller_output = run_goal_distiller(
                    categories=settings_obj.categories,
                    topics=settings_obj.topics,
                    content_interest=settings_obj.content_interest,
                    filtering_goal=settings_obj.filtering_goal
                )
                settings_obj.distilled_criteria = distiller_output.distilled_criteria
                settings_obj.lexical_query = distiller_output.lexical_query

                if settings_obj.filtering_goal:
                    embeddings = await specter2_embed_batch([
                        {"title": settings_obj.filtering_goal, "abstract": settings_obj.filtering_goal}
                    ])
                    settings_obj.goal_embedding = embeddings[0]

                await session.commit()
        await engine.dispose()

    _run_async(_run())


# ─────────────────────────────────────────────────────────────────────
# Main Pipeline: Cascade Agentic Funnel (v2)
# ─────────────────────────────────────────────────────────────────────

@celery_app.task(name="pipeline.run_discovery", bind=True)
def trigger_agent_discovery(self, user_id: str):
    """Cascade pipeline: RRF → Phase 1 (Evaluator+Critique) → Marker → Phase 2 (Deep Reader) → Top Picks."""
    from app.worker.arxiv_scraper import fetch_arxiv_papers, ingest_papers
    from app.db.retrieval import perform_hybrid_rrf_search
    from app.agents.graph import phase1_graph, run_deep_reader
    from app.worker.modal_client import marker_extract_pdf
    from app.db.models import UserSettings, UserPaper, Paper, FeedbackMemory, User
    from app.worker.notifications import notify_top_picks
    import uuid
    import logging

    logger = logging.getLogger(__name__)

    def _update(stage: str, progress: int):
        self.update_state(state="PROGRESS", meta={"stage": stage, "progress": progress})

    async def _run():
        engine, SessionLocal = _make_session()

        try:
            async with SessionLocal() as session:
                # ── 0. Load user settings ──────────────────────────────
                _update("Loading settings", 5)
                result = await session.execute(select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id)))
                user_settings = result.scalars().first()
                categories = user_settings.categories if user_settings and user_settings.categories else ["cs.AI"]

                # ── 1. Scrape + ingest ArXiv papers ────────────────────
                _update("Fetching ArXiv papers", 10)
                cat_query = "+OR+".join(f"cat:{cat}" for cat in categories)
                logger.info(f"[pipeline:{user_id[:8]}] Fetching ArXiv papers for: {categories}")
                papers = fetch_arxiv_papers(cat_query, max_results=200)
                logger.info(f"[pipeline:{user_id[:8]}] Fetched {len(papers)} papers, ingesting...")
                _update("Ingesting papers", 15)
                await ingest_papers(session, papers)

                # ── 2. Validate prerequisites ──────────────────────────
                if not user_settings or not user_settings.distilled_criteria:
                    logger.warning(f"[pipeline:{user_id[:8]}] ABORTING — no distilled_criteria")
                    return

                # Load feedback memory
                fm_result = await session.execute(
                    select(FeedbackMemory).where(FeedbackMemory.user_id == uuid.UUID(user_id))
                )
                fm = fm_result.scalars().first()
                feedback_str = fm.summarized_feedback if fm and fm.summarized_feedback else ""

                # ── 3. Hybrid RRF Search → 30 candidates ──────────────
                _update("Running hybrid search", 20)
                query_embedding = user_settings.goal_embedding
                if query_embedding is None:
                    from app.worker.modal_client import specter2_embed_batch
                    if user_settings.filtering_goal:
                        logger.info(f"[pipeline:{user_id[:8]}] goal_embedding missing, embedding on-the-fly")
                        embeddings = await specter2_embed_batch([
                            {"title": user_settings.filtering_goal, "abstract": user_settings.filtering_goal}
                        ])
                        query_embedding = embeddings[0]
                    else:
                        query_embedding = [0.0] * 768

                logger.info(f"[pipeline:{user_id[:8]}] Running hybrid RRF search (limit=30)...")
                candidates = await perform_hybrid_rrf_search(
                    session=session,
                    query_text=user_settings.lexical_query or user_settings.filtering_goal or "AI Agents",
                    query_embedding=query_embedding,
                    limit=30,
                )
                logger.info(f"[pipeline:{user_id[:8]}] RRF returned {len(candidates)} candidates")

                # ── 4. Phase 1: Evaluator + Critique (abstract-only) ──
                _update("Phase 1: Evaluating abstracts", 30)
                phase1_results = []  # list of (candidate, final_state)

                total_cands = len(candidates)
                for i, cand in enumerate(candidates):
                    _update(f"Phase 1: Paper {i+1}/{total_cands}", 30 + int(20 * i / max(total_cands, 1)))
                    # Dedup: skip existing UserPaper entries
                    existing = await session.execute(
                        select(UserPaper).where(
                            UserPaper.user_id == uuid.UUID(user_id),
                            UserPaper.paper_id == cand["id"],
                        )
                    )
                    if existing.scalars().first():
                        continue

                    try:
                        state_input = {
                            "user_id": user_id,
                            "distilled_criteria": user_settings.distilled_criteria,
                            "feedback_memory": feedback_str,
                            "current_paper_id": cand["id"],
                            "raw_abstract": cand["abstract"],
                            "pdf_url": cand.get("pdf_url"),
                            "evaluator_decision": "borderline",
                            "evaluator_score": 0.0,
                            "evaluator_reasonbook": "",
                            "critique_decision": True,
                            "critique_reasonbook": "",
                        }

                        final_state = await phase1_graph.ainvoke(state_input)

                        decision = final_state.get("evaluator_decision")
                        accepted = False
                        if decision == "accept":
                            accepted = True
                        elif decision == "borderline" and final_state.get("critique_decision") is True:
                            accepted = True

                        logger.info(
                            f"[pipeline:{user_id[:8]}] Phase1 {i+1}/{len(candidates)} "
                            f"'{cand['id']}' → {decision} (score={final_state.get('evaluator_score')}) "
                            f"{'→ ACCEPTED' if accepted else '→ REJECTED'}"
                        )

                        if accepted:
                            phase1_results.append((cand, final_state))
                        else:
                            # Rejected by evaluator/critique — save as rejected
                            session.add(UserPaper(
                                user_id=uuid.UUID(user_id),
                                paper_id=cand["id"],
                                status="rejected",
                                agent_score=final_state.get("evaluator_score"),
                            ))

                    except Exception as e:
                        logger.error(f"[pipeline:{user_id[:8]}] Phase1 failed on '{cand['id']}': {e}", exc_info=True)
                        continue

                await session.commit()
                logger.info(f"[pipeline:{user_id[:8]}] Phase 1 complete — {len(phase1_results)} accepted")

                if not phase1_results:
                    logger.info(f"[pipeline:{user_id[:8]}] No papers passed Phase 1, pipeline done")
                    return

                _update("Sorting candidates", 55)
                # ── 5. Sort by evaluator score → take top K ───────────
                deep_scan_limit = user_settings.deep_scan_limit or 10
                phase1_results.sort(key=lambda x: x[1].get("evaluator_score", 0), reverse=True)
                top_k = phase1_results[:deep_scan_limit]

                # Save remaining accepted papers (beyond top K) directly to feed without deep reading
                for cand, state in phase1_results[deep_scan_limit:]:
                    session.add(UserPaper(
                        user_id=uuid.UUID(user_id),
                        paper_id=cand["id"],
                        status="feed",
                        agent_score=state.get("evaluator_score"),
                        agent_explanation=f"Passed abstract screening (score: {state.get('evaluator_score', 0):.1f}/10). "
                                          f"Not deep-scanned due to scan limit ({deep_scan_limit}).",
                    ))
                await session.commit()

                logger.info(
                    f"[pipeline:{user_id[:8]}] Top {len(top_k)} papers selected for deep scan "
                    f"(deep_scan_limit={deep_scan_limit})"
                )

                # ── 6. Marker: parallel PDF extraction ─────────────────
                async def extract_pdf(cand_data):
                    pdf_url = cand_data.get("pdf_url")
                    if not pdf_url:
                        return cand_data.get("abstract", "")
                    try:
                        md = await marker_extract_pdf(pdf_url)
                        return md if md else cand_data.get("abstract", "")
                    except Exception as e:
                        logger.error(f"[pipeline:{user_id[:8]}] Marker failed for {cand_data['id']}: {e}")
                        return cand_data.get("abstract", "")

                _update(f"Extracting PDFs ({len(top_k)} papers)", 60)
                logger.info(f"[pipeline:{user_id[:8]}] Starting parallel Marker extraction for {len(top_k)} papers...")
                markdown_results = await asyncio.gather(*[extract_pdf(c) for c, _ in top_k])
                logger.info(f"[pipeline:{user_id[:8]}] Marker extraction complete")

                # ── 7. Phase 2: parallel Deep Reader ───────────────────
                async def deep_read(markdown_text, cand_data, eval_state):
                    try:
                        return await run_deep_reader(
                            markdown=markdown_text,
                            distilled_criteria=user_settings.distilled_criteria,
                            feedback_memory=feedback_str,
                        )
                    except Exception as e:
                        logger.error(f"[pipeline:{user_id[:8]}] Deep Reader failed for {cand_data['id']}: {e}")
                        # Fallback: use evaluator score, accept to feed
                        return {
                            "decision": "accept",
                            "score": eval_state.get("evaluator_score", 5.0),
                            "explanation": "Deep reading failed — scored by abstract evaluation only.",
                        }

                _update(f"Phase 2: Deep reading ({len(top_k)} papers)", 75)
                logger.info(f"[pipeline:{user_id[:8]}] Starting parallel Deep Reader for {len(top_k)} papers...")
                deep_results = await asyncio.gather(*[
                    deep_read(md, cand, state)
                    for md, (cand, state) in zip(markdown_results, top_k)
                ])
                logger.info(f"[pipeline:{user_id[:8]}] Deep Reader complete")

                _update("Saving results", 90)
                # ── 8. Save results + select top 3 picks ──────────────
                feed_papers = []  # (UserPaper, Paper) for notification

                for (cand, eval_state), md_text, dr_result in zip(top_k, markdown_results, deep_results):
                    dr_decision = dr_result.get("decision", "reject")
                    dr_score = dr_result.get("score", 0.0)

                    # Deep Reader can reject papers that abstract accepted
                    if dr_decision == "reject" or dr_score < 5.0:
                        status = "rejected"
                    else:
                        status = "feed"

                    up = UserPaper(
                        user_id=uuid.UUID(user_id),
                        paper_id=cand["id"],
                        status=status,
                        agent_score=dr_score,
                        agent_explanation=dr_result.get("explanation"),
                        extracted_markdown=md_text if md_text != cand.get("abstract", "") else None,
                    )
                    session.add(up)

                    if status == "feed":
                        feed_papers.append((up, cand, dr_score))

                    logger.info(
                        f"[pipeline:{user_id[:8]}] Deep Reader '{cand['id']}' → {status} "
                        f"(eval_score={eval_state.get('evaluator_score')}, deep_score={dr_score})"
                    )

                # Mark top 3 as top picks (only if score >= 7.0)
                TOP_PICK_MIN_SCORE = 7.0
                feed_papers.sort(key=lambda x: x[2], reverse=True)
                top_picks_count = 0
                for up, cand, score in feed_papers[:3]:
                    if score >= TOP_PICK_MIN_SCORE:
                        up.is_top_pick = True
                        top_picks_count += 1
                        logger.info(f"[pipeline:{user_id[:8]}] TOP PICK: '{cand['id']}' (score={score})")
                    else:
                        logger.info(f"[pipeline:{user_id[:8]}] Skipped top pick '{cand['id']}' — score {score} < {TOP_PICK_MIN_SCORE}")

                await session.commit()

                total_feed = len(feed_papers)
                total_rejected_phase2 = len(top_k) - total_feed
                logger.info(
                    f"[pipeline:{user_id[:8]}] Pipeline complete — "
                    f"Phase1: {len(phase1_results)} accepted, "
                    f"Deep scanned: {len(top_k)}, "
                    f"Feed: {total_feed}, "
                    f"Rejected by Deep Reader: {total_rejected_phase2}, "
                    f"Top picks: {top_picks_count}"
                )

                _update("Sending notifications", 95)
                # ── 9. Notifications for top picks ─────────────────────
                top_pick_entries = [
                    (up, cand) for up, cand, score in feed_papers[:3]
                    if score >= TOP_PICK_MIN_SCORE
                ]
                if top_pick_entries:
                    user_result = await session.execute(
                        select(User).where(User.id == uuid.UUID(user_id))
                    )
                    user_obj = user_result.scalars().first()

                    # Use notification_email if set, otherwise fall back to login email
                    notify_email = user_settings.notification_email or user_obj.email

                    top_papers_data = [
                        {
                            "title": cand["title"],
                            "source_url": cand.get("source_url"),
                            "agent_score": up.agent_score,
                            "agent_explanation": up.agent_explanation,
                        }
                        for up, cand in top_pick_entries
                    ]
                    notify_top_picks(notify_email, top_papers_data)
                    logger.info(f"[pipeline:{user_id[:8]}] Notification sent to {notify_email}")

        except Exception as e:
            logger.error(f"[pipeline:{user_id[:8]}] TASK FAILED: {e}", exc_info=True)
            raise
        finally:
            await engine.dispose()

    _run_async(_run())


# ─────────────────────────────────────────────────────────────────────
# Library Deep Explanation (unchanged — uses cached markdown)
# ─────────────────────────────────────────────────────────────────────

@celery_app.task(name="library.generate_deep_explanation")
def generate_deep_explanation(user_paper_id: str, user_id: str):
    """Generates a deep, PDF-based explanation for an accepted library paper.

    Steps: Check cached markdown → (Marker if needed) → section classifier → LLM deep explanation → cache.
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
        engine, SessionLocal = _make_session()

        async with SessionLocal() as session:
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

            settings_result = await session.execute(
                select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id))
            )
            user_settings = settings_result.scalars().first()
            level = user_settings.library_explanation_level if user_settings else "professional"
            content_interest = user_settings.content_interest if user_settings else []
            filtering_goal = user_settings.filtering_goal if user_settings else ""

            # Step 1: Use cached markdown from pipeline, or call Marker
            extracted_text = user_paper.extracted_markdown
            if not extracted_text:
                logger.info(f"No cached markdown for {user_paper_id}, calling Marker...")
                extracted_text = await marker_extract_pdf(paper.pdf_url)
                if extracted_text:
                    # Cache for future use
                    user_paper.extracted_markdown = extracted_text
                else:
                    extracted_text = paper.abstract

            # Step 2: Section classifier filters by content_interest
            filtered_text = classify_sections(extracted_text, content_interest or [])

            # Step 3: Deep explanation via LLM
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

            output = (prompt | structured).invoke({
                "level_instruction": level_instructions.get(level, level_instructions["professional"]),
                "filtering_goal": filtering_goal or "General AI research",
                "title": paper.title,
                "authors": authors_str,
                "filtered_text": filtered_text,
            })

            # Upsert explanation
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


# ─────────────────────────────────────────────────────────────────────
# Memory Summarizer
# ─────────────────────────────────────────────────────────────────────

@celery_app.task(name="pipeline.trigger_memory_summarizer")
def run_memory_summarizer(user_id: str, new_comment: str):
    """Summarizes accumulated rejection comments into feedback_memory."""
    from app.db.models import FeedbackMemory
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from app.agents.schemas import MemoryOutput
    import uuid

    async def _run():
        engine, SessionLocal = _make_session()

        async with SessionLocal() as session:
            result = await session.execute(
                select(FeedbackMemory).where(FeedbackMemory.user_id == uuid.UUID(user_id))
            )
            memory = result.scalars().first()

            if not memory:
                memory = FeedbackMemory(
                    user_id=uuid.UUID(user_id),
                    summarized_feedback="",
                    rejection_count=0,
                )
                session.add(memory)

            memory.rejection_count = (memory.rejection_count or 0) + 1
            existing_feedback = memory.summarized_feedback or ""

            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, api_key=settings.OPENAI_API_KEY)
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
                )),
            ])

            result = (prompt | structured).invoke({
                "existing": existing_feedback if existing_feedback else "No prior feedback.",
                "new_comment": new_comment,
            })

            memory.summarized_feedback = result.summarized_feedback
            await session.commit()
        await engine.dispose()

    _run_async(_run())
