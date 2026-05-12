from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
import asyncio

from typing import Optional

from fastapi import APIRouter, Cookie, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel

from .chunks import LOAD_STATUS, ChunkStore, start_load
from .config import PAGE_SIZE, RANDOM_PACK_ID, RANDOM_PACK_SIZE
from .logging_mod import write_raw_logs
from .state import SessionState, get_or_create, sessions
from .storage import Pack, Storage
from .grammar_assistant import (
    generate_exercise, validate_answer, submit_custom_exercise, get_enabled_types,
)
from .grammar_assistant.models import ExerciseType, Exercise, ValidationResult

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

storage: Storage = Storage.load()
chunk_store: ChunkStore = ChunkStore()


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        from .grammar_assistant.tools.language_tool import _get_tool
        await asyncio.to_thread(_get_tool)
    except Exception:
        pass
    yield
    await storage.wikibase.aclose()
    try:
        from .grammar_assistant.tools.language_tool import close_tool
        await asyncio.to_thread(close_tool)
    except Exception:
        pass


app = FastAPI(title="VocabGuesser v0", lifespan=lifespan)

VALID_FEEDBACK_MARKS = {"like", "dislike", "confused"}
RATING_CATEGORIES = ("usefulness", "comfort", "speed")


def _ensure_session(sid: str | None) -> tuple[str, SessionState, bool]:
    """Return (sid, state, is_new). Generates a new sid if missing."""
    if not sid:
        sid = uuid.uuid4().hex
        state = SessionState.new()
        sessions[sid] = state
        write_raw_logs({"sid": sid, "event": "session_created"})
        return sid, state, True
    state, created = get_or_create(sid)
    if created:
        write_raw_logs({"sid": sid, "event": "session_created", "reason": "restart_recovery"})
    return sid, state, False


def _attach_sid_cookie(response: Response, sid: str, is_new: bool) -> None:
    if is_new:
        response.set_cookie(
            key="sid",
            value=sid,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
        )


def _require_active(state: SessionState):
    if state.active_pack is None:
        raise HTTPException(status_code=400, detail="No active pack")
    return state.active_pack


@app.get("/", response_class=HTMLResponse)
async def page_packs(
    request: Request,
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, state, is_new = _ensure_session(sid)
    packs = storage.list_packs()
    presets = storage.list_presets()
    in_progress = {
        pid: prog
        for pid, prog in state.progress_by_pack.items()
        if not prog.is_complete()
    }
    last_progress = state.active_pack or (
        next(iter(in_progress.values())) if in_progress else None
    )
    default_preset_name = (
        last_progress.preset_name if last_progress else presets[0].preset_name
    )
    unknown_count = sum(1 for w in storage.words.values() if not w.known)
    response = templates.TemplateResponse(
        request,
        "packs.html",
        {
            "packs": packs,
            "presets": presets,
            "in_progress": in_progress,
            "default_preset_name": default_preset_name,
            "unknown_count": unknown_count,
        },
    )
    _attach_sid_cookie(response, sid, is_new)
    return response


@app.post("/start")
async def start_pack(
    pack_id: Annotated[int, Form()],
    preset_name: Annotated[str, Form()],
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, state, is_new = _ensure_session(sid)
    pack = storage.get_pack(pack_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="Pack not found")
    preset = storage.get_preset(preset_name)
    if preset is None:
        raise HTTPException(status_code=400, detail=f"Unknown preset: {preset_name}")
    progress, was_reset = state.start_pack(pack, preset)
    write_raw_logs({
        "sid": sid,
        "event": "pack_started",
        "pack_id": pack_id,
        "preset_name": preset.preset_name,
        "actions": preset.actions,
        "reset": was_reset,
    })
    response = RedirectResponse(url="/card", status_code=303)
    _attach_sid_cookie(response, sid, is_new)
    return response


@app.post("/start-random")
async def start_random(
    preset_name: Annotated[str, Form()],
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, state, is_new = _ensure_session(sid)
    preset = storage.get_preset(preset_name)
    if preset is None:
        raise HTTPException(status_code=400, detail=f"Unknown preset: {preset_name}")
    words = storage.sample_unknown(RANDOM_PACK_SIZE)
    if not words:
        raise HTTPException(status_code=400, detail="No unknown words in dictionary")
    pack = Pack(
        pack_id=RANDOM_PACK_ID,
        pack_name=f"Random · {len(words)} words",
        word_ids=tuple(w.word_id for w in words),
    )
    progress, was_reset = state.start_pack(pack, preset)
    write_raw_logs({
        "sid": sid,
        "event": "random_pack_started",
        "preset_name": preset.preset_name,
        "word_count": len(words),
        "word_ids": list(pack.word_ids),
        "reset": was_reset,
    })
    response = RedirectResponse(url="/card", status_code=303)
    _attach_sid_cookie(response, sid, is_new)
    return response


@app.get("/card", response_class=HTMLResponse)
async def page_card(
    request: Request,
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, state, is_new = _ensure_session(sid)
    progress = state.active_pack
    if progress is None:
        response = RedirectResponse(url="/", status_code=303)
        _attach_sid_cookie(response, sid, is_new)
        return response

    if progress.is_complete():
        response = RedirectResponse(url="/done", status_code=303)
        _attach_sid_cookie(response, sid, is_new)
        return response

    word_id = progress.peek_current()
    word = storage.get_word(word_id) if word_id is not None else None
    pack = storage.get_pack(progress.pack_id) or Pack(
        pack_id=progress.pack_id,
        pack_name=progress.pack_name or "Random session",
        word_ids=(),
    )

    if word is not None and progress.current_task is None:
        chunk = chunk_store.get_chunk_for_word(word.word_id)
        session_wids = list(progress.word_info.keys())
        other_words = [w for wid in session_wids if (w := storage.get_word(wid)) and wid != word.word_id]
        progress.generate_task(word, other_words, chunk)

    

    response = templates.TemplateResponse(
        request,
        "card.html",
        {
            "pack": pack,
            "progress": progress,
            "word": word,
            "task": progress.current_task,
            "remaining_count": len(progress.remaining),
            "learned_count": len(progress.learned),
            "current_familiarity": progress.current_familiarity(),
        },
    )
    _attach_sid_cookie(response, sid, is_new)
    return response


@app.post("/card/action")
async def card_action(
    action: Annotated[str, Form()],
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, state, is_new = _ensure_session(sid)
    progress = _require_active(state)
    if action not in progress.actions:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    result = progress.apply_action(action)
    if result is not None:
        write_raw_logs({
            "sid": sid,
            "event": "word_action_applied",
            "pack_id": progress.pack_id,
            "preset_name": progress.preset_name,
            "word_id": result.word_id,
            "action": result.action,
            "delta": result.delta,
            "new_familiarity": result.new_familiarity,
            "removed": result.removed,
        })
        if progress.is_complete():
            write_raw_logs({
                "sid": sid,
                "event": "pack_completed",
                "pack_id": progress.pack_id,
                "preset_name": progress.preset_name,
                "learned_count": len(progress.learned),
            })
    response = RedirectResponse(url="/card", status_code=303)
    _attach_sid_cookie(response, sid, is_new)
    return response



@app.post("/card/feedback")
async def card_feedback(
    mark: Annotated[str, Form()],
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, state, is_new = _ensure_session(sid)
    progress = _require_active(state)
    if mark not in VALID_FEEDBACK_MARKS:
        raise HTTPException(status_code=400, detail=f"Unknown mark: {mark}")
    write_raw_logs({
        "sid": sid,
        "event": "pack_marked",
        "pack_id": progress.pack_id,
        "preset_name": progress.preset_name,
        "current_word_id": progress.current,
        "mark": mark,
    })
    response = RedirectResponse(url="/card", status_code=303)
    _attach_sid_cookie(response, sid, is_new)
    return response


@app.post("/card/task-response")
async def card_task_response(
    answer: Annotated[str, Form()] = "",
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, state, is_new = _ensure_session(sid)
    progress = _require_active(state)
    result = progress.apply_task_response(answer)
    if result is None:
        raise HTTPException(status_code=400, detail="No active task")
    if result is not None:
        write_raw_logs({
            "sid": sid,
            "event": "task_response",
            "pack_id": progress.pack_id,
            "task_type": result.task_type,
            "correct": result.correct,
            "correct_word": result.correct_word,
            "delta": result.delta,
            "removed": result.removed,
        })
        if progress.is_complete():
            write_raw_logs({
                "sid": sid,
                "event": "pack_completed",
                "pack_id": progress.pack_id,
                "preset_name": progress.preset_name,
                "learned_count": len(progress.learned),
            })
    payload = {
        "correct": result.correct,
        "correct_word": result.correct_word,
        "task_type": result.task_type,
        "removed": result.removed,
    }
    response = JSONResponse(payload)
    _attach_sid_cookie(response, sid, is_new)
    return response


# --- Corpus / chunk loading ---------------------------------------------------


@app.get("/corpus", response_class=HTMLResponse)
async def page_corpus(
    request: Request,
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, state, is_new = _ensure_session(sid)
    word_ids = list(storage.words.keys())
    coverage = chunk_store.coverage_stats(word_ids)
    # Build histogram buckets: 0, 1, 2-4, 5-9, 10+
    hist = coverage["histogram"]
    buckets = {"0": 0, "1": 0, "2-4": 0, "5-9": 0, "10+": 0}
    for n in hist.values():
        if n == 0:
            buckets["0"] += 1
        elif n == 1:
            buckets["1"] += 1
        elif n <= 4:
            buckets["2-4"] += 1
        elif n <= 9:
            buckets["5-9"] += 1
        else:
            buckets["10+"] += 1
    response = templates.TemplateResponse(
        request,
        "corpus.html",
        {
            "total_chunks": chunk_store.total_chunks(),
            "total_mb": chunk_store.total_bytes() / 1_000_000,
            "coverage": coverage,
            "buckets": buckets,
            "load_status": dict(LOAD_STATUS),
        },
    )
    _attach_sid_cookie(response, sid, is_new)
    return response


@app.post("/corpus/load")
async def corpus_load(
    target_mb: Annotated[int, Form()] = 100,
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, _state, is_new = _ensure_session(sid)
    target_mb = max(10, min(500, target_mb))
    word_map = {wid: w.word for wid, w in storage.words.items()}
    start_load(chunk_store, word_map, target_mb=target_mb)
    write_raw_logs({"sid": sid, "event": "corpus_load_started", "target_mb": target_mb})
    response = RedirectResponse(url="/corpus", status_code=303)
    _attach_sid_cookie(response, sid, is_new)
    return response


@app.get("/corpus/status")
async def corpus_status():
    return JSONResponse(dict(LOAD_STATUS))


@app.get("/done", response_class=HTMLResponse)
async def page_done(
    request: Request,
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, state, is_new = _ensure_session(sid)
    progress = state.active_pack
    if progress is not None:
        pack = storage.get_pack(progress.pack_id) or Pack(
            pack_id=progress.pack_id,
            pack_name=progress.pack_name or "Random session",
            word_ids=(),
        )
    else:
        pack = None
    learned_count = len(progress.learned) if progress is not None else 0
    response = templates.TemplateResponse(
        request,
        "done.html",
        {
            "pack": pack,
            "progress": progress,
            "learned_count": learned_count,
            "rating_categories": RATING_CATEGORIES,
        },
    )
    _attach_sid_cookie(response, sid, is_new)
    return response


def _parse_rating(name: str, value: str) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid {name}") from e
    if not 1 <= n <= 5:
        raise HTTPException(status_code=400, detail=f"{name} must be 1–5")
    return n


@app.post("/done/rate")
async def done_rate(
    usefulness: Annotated[str, Form()],
    comfort: Annotated[str, Form()],
    speed: Annotated[str, Form()],
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, state, is_new = _ensure_session(sid)
    progress = state.active_pack
    if progress is None:
        raise HTTPException(status_code=400, detail="No pack to rate")
    ratings = {
        "usefulness": _parse_rating("usefulness", usefulness),
        "comfort": _parse_rating("comfort", comfort),
        "speed": _parse_rating("speed", speed),
    }
    write_raw_logs({
        "sid": sid,
        "event": "pack_rated",
        "pack_id": progress.pack_id,
        "preset_name": progress.preset_name,
        "learned_count": len(progress.learned),
        **ratings,
    })
    state.clear_active()
    response = RedirectResponse(url="/", status_code=303)
    _attach_sid_cookie(response, sid, is_new)
    return response


# --- Dictionary (words) ----------------------------------------------------


_VALID_SORTS = {"id", "word", "chunks"}
_VALID_DIRS  = {"asc", "desc"}


@app.get("/words", response_class=HTMLResponse)
async def page_words(
    request: Request,
    page: int = 1,
    sort: str = "id",
    dir: str = "asc",
    added: int = 0,
    duplicates: str = "",
    not_found: str = "",
    sid: Annotated[str | None, Cookie()] = None,
):
    if sort not in _VALID_SORTS:
        sort = "id"
    if dir not in _VALID_DIRS:
        dir = "asc"
    sid, state, is_new = _ensure_session(sid)
    all_words = storage.list_words()
    total = len(all_words)
    known_count = sum(1 for w in all_words if w.known)

    word_ids = [w.word_id for w in all_words]
    counts = chunk_store.chunk_counts(word_ids)

    if sort == "word":
        all_words.sort(key=lambda w: w.word.lower(), reverse=(dir == "desc"))
    elif sort == "chunks":
        all_words.sort(key=lambda w: counts.get(w.word_id, 0), reverse=(dir == "desc"))
    else:
        all_words.sort(key=lambda w: w.word_id, reverse=(dir == "desc"))

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    words = all_words[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    response = templates.TemplateResponse(
        request,
        "words.html",
        {
            "words": words,
            "counts": counts,
            "total": total,
            "known_count": known_count,
            "page": page,
            "total_pages": total_pages,
            "sort": sort,
            "dir": dir,
            "added_count": added,
            "duplicates": [d for d in duplicates.split(",") if d],
            "not_found": [d for d in not_found.split(",") if d],
        },
    )
    _attach_sid_cookie(response, sid, is_new)
    return response


@app.get("/words/{word_id}/examples")
async def word_examples(word_id: int):
    chunks = chunk_store.get_chunks_for_word(word_id, limit=5)
    return JSONResponse({"chunks": chunks})


@app.post("/card/add-word")
async def card_add_word(
    word: Annotated[str, Form()],
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, state, is_new = _ensure_session(sid)
    text = word.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty word")
    w, status = await storage.add_word(text)
    if w is not None and status == "created":
        chunk_store.index_word(w.word_id, w.word)
    queued = False
    if w is not None and state.active_pack is not None:
        progress = state.active_pack
        already_tracked = (
            w.word_id in progress.learned
            or w.word_id in progress.remaining
            or w.word_id == progress.current
        )
        if not already_tracked:
            progress.add_new_word(w.word_id)
            queued = True
    write_raw_logs({
        "sid": sid,
        "event": "dictionary_word_" + status,
        "word": text,
        "word_id": w.word_id if w else None,
        "queued_to_session": queued,
    })
    payload = {
        "added": status == "created",
        "duplicate": status == "duplicate",
        "not_found": status == "not_found",
        "queued": queued,
        "word_id": w.word_id if w else None,
        "word": w.word if w else text,
    }
    response = JSONResponse(payload)
    _attach_sid_cookie(response, sid, is_new)
    return response


@app.post("/words/add")
async def words_add(
    word: Annotated[str, Form()],
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, _state, is_new = _ensure_session(sid)
    text = word.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty word")
    w, status = await storage.add_word(text)
    if w is not None and status == "created":
        chunk_store.index_word(w.word_id, w.word)
    write_raw_logs({
        "sid": sid,
        "event": "dictionary_word_" + status,
        "word": text,
        "word_id": w.word_id if w else None,
    })
    payload = {
        "added": status == "created",
        "duplicate": status == "duplicate",
        "not_found": status == "not_found",
        "word_id": w.word_id if w else None,
        "word": w.word if w else text,
    }
    response = JSONResponse(payload)
    _attach_sid_cookie(response, sid, is_new)
    return response


@app.post("/words/bulk-add")
async def words_bulk_add(
    words: Annotated[str, Form()],
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, _state, is_new = _ensure_session(sid)
    lines = words.splitlines()
    added, dups, not_found = await storage.add_words_bulk(lines)
    for w in added:
        chunk_store.index_word(w.word_id, w.word)
    write_raw_logs({
        "sid": sid,
        "event": "dictionary_words_bulk_added",
        "added_count": len(added),
        "duplicate_count": len(dups),
        "not_found_count": len(not_found),
        "added_word_ids": [w.word_id for w in added],
    })
    from urllib.parse import quote
    qs_dups = ",".join(dups[:20])
    qs_nf = ",".join(not_found[:20])
    url = f"/words?added={len(added)}"
    if qs_dups:
        url += f"&duplicates={quote(qs_dups)}"
    if qs_nf:
        url += f"&not_found={quote(qs_nf)}"
    response = RedirectResponse(url=url, status_code=303)
    _attach_sid_cookie(response, sid, is_new)
    return response


@app.post("/words/{word_id}/toggle")
async def words_toggle(
    word_id: int,
    page: Annotated[int, Form()] = 1,
    sort: Annotated[str, Form()] = "id",
    dir: Annotated[str, Form()] = "asc",
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, _state, is_new = _ensure_session(sid)
    w = storage.get_word(word_id)
    if w is None:
        raise HTTPException(status_code=404, detail="Word not found")
    updated = await storage.set_known(word_id, not w.known)
    write_raw_logs({
        "sid": sid,
        "event": "dictionary_word_status_changed",
        "word_id": word_id,
        "known": updated.known if updated else None,
    })
    response = RedirectResponse(url=f"/words?page={page}&sort={sort}&dir={dir}", status_code=303)
    _attach_sid_cookie(response, sid, is_new)
    return response


# --- Grammar assistant -------------------------------------------------------


grammar_router = APIRouter(prefix="/grammar", tags=["grammar"])


class GenerateRequest(BaseModel):
    exercise_type: Optional[ExerciseType] = None
    user_id: Optional[str] = None


class ValidateRequest(BaseModel):
    exercise: Exercise
    user_answer: str
    user_id: Optional[str] = None


class CustomRequest(BaseModel):
    user_sentence: str
    exercise_type: ExerciseType
    user_id: Optional[str] = None


@grammar_router.post("/exercise", response_model=Exercise)
async def post_exercise(req: GenerateRequest):
    try:
        return await asyncio.to_thread(generate_exercise, req.exercise_type, req.user_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@grammar_router.post("/validate", response_model=ValidationResult)
async def post_validate(req: ValidateRequest):
    try:
        return await asyncio.to_thread(validate_answer, req.exercise, req.user_answer, req.user_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@grammar_router.post("/custom-exercise", response_model=Exercise)
async def post_custom(req: CustomRequest):
    try:
        return await asyncio.to_thread(submit_custom_exercise, req.user_sentence, req.exercise_type, req.user_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@grammar_router.get("/types")
async def get_types():
    return {"types": [t.value for t in get_enabled_types()]}


@grammar_router.get("", response_class=HTMLResponse)
async def page_grammar(
    request: Request,
    sid: Annotated[str | None, Cookie()] = None,
):
    sid, _, is_new = _ensure_session(sid)
    response = templates.TemplateResponse(request, "grammar.html", {})
    _attach_sid_cookie(response, sid, is_new)
    return response


app.include_router(grammar_router)


# --- Random word add ---------------------------------------------------------


@app.post("/card/add-random")
async def card_add_random(
    n: Annotated[int, Form()] = 5,
    sid: Annotated[str | None, Cookie()] = None,
):
    import random as _random
    sid, state, is_new = _ensure_session(sid)
    progress = _require_active(state)
    already = progress.learned | set(progress.remaining)
    if progress.current is not None:
        already.add(progress.current)
    candidates = [w for w in storage.words.values() if not w.known and w.word_id not in already]
    sample = _random.sample(candidates, min(n, len(candidates)))
    for w in sample:
        progress.add_new_word(w.word_id)
    write_raw_logs({
        "sid": sid,
        "event": "session_words_added_random",
        "pack_id": progress.pack_id,
        "added_count": len(sample),
        "word_ids": [w.word_id for w in sample],
    })
    payload = {"added": len(sample), "words": [w.word for w in sample]}
    response = JSONResponse(payload)
    _attach_sid_cookie(response, sid, is_new)
    return response
