import os
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from agent.agent import Session, execute_approved
from agent.datasource import DataError, MemoryDataSource
from agent.events import ApprovalStore, EventLog, metrics
from agent.llm import make_client
from agent.orchestrator import make_orchestrator
from agent.tools import default_registry

ROOT = Path(__file__).resolve().parent.parent


class ApiError(Exception):
    def __init__(self, status: int, error: str, message: str):
        self.status, self.error, self.message = status, error, message


class NewSession(BaseModel):
    tenant_id: str
    client_id: str
    channel: str = "chat"


class NewMessage(BaseModel):
    text: str


class Decision(BaseModel):
    approve: bool
    note: str | None = None
    by: str


def create_app(ds=None, llm=None, now_fn=None, orchestrator=None) -> FastAPI:
    now_fn = now_fn or (lambda: datetime.now(ZoneInfo("Europe/Kyiv")))
    ds = ds or MemoryDataSource.from_file(Path(__file__).parent / "seed.json", now_fn(), now_fn=now_fn)
    app = FastAPI(title="Support agent")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    st = app.state
    st.ds, st.events, st.approvals = ds, EventLog(now_fn), ApprovalStore(now_fn)
    st.sessions, st.locks = {}, {}
    st.llm, st.counter, st.guard = llm, 0, threading.Lock()
    st.orchestrator, st.orch_ready = orchestrator, orchestrator is not None

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError):
        return JSONResponse({"error": e.error, "message": e.message}, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, e: RequestValidationError):
        return JSONResponse({"error": "validation", "message": "Некоректний запит.",
                             "detail": jsonable_encoder(e.errors())}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, e: StarletteHTTPException):
        codes = {404: ("not_found", "Не знайдено."), 405: ("method_not_allowed", "Метод не підтримується.")}
        error, message = codes.get(e.status_code, ("http_error", "Помилка запиту."))
        return JSONResponse({"error": error, "message": message}, status_code=e.status_code)

    def lookup(call, *args):
        try:
            return call(*args)
        except DataError as e:
            raise ApiError(404, e.code, e.message) from None

    def session_of(session_id: str) -> Session:
        s = st.sessions.get(session_id)
        if s is None:
            raise ApiError(404, "not_found", f"Сесію {session_id} не знайдено")
        return s

    @app.post("/sessions")
    def create_session(body: NewSession):
        lookup(ds.get_client, body.tenant_id, body.client_id)
        with st.guard:
            if st.llm is None:
                try:
                    st.llm = make_client()
                except RuntimeError as e:
                    raise ApiError(503, "llm_unavailable", str(e)) from None
            if not st.orch_ready:
                st.orchestrator, st.orch_ready = make_orchestrator(), True
            st.counter += 1
            sid = f"s-{st.counter}"
        st.sessions[sid] = Session(sid, body.tenant_id, body.client_id, body.channel, ds,
                                   st.events, st.approvals, st.llm, default_registry(), now_fn, st.orchestrator,
                                   os.environ.get("AGENT_MODEL") or getattr(st.llm, "model", None))
        st.locks[sid] = threading.Lock()
        return {"session_id": sid}

    @app.post("/sessions/{session_id}/messages")
    async def post_message(session_id: str, body: NewMessage):
        session = session_of(session_id)
        lock = st.locks[session_id]
        if not lock.acquire(blocking=False):
            raise ApiError(409, "busy", "Агент ще обробляє попереднє повідомлення")
        try:
            reply = await run_in_threadpool(session.send, body.text)
        finally:
            lock.release()
        return {"reply": reply}

    @app.get("/sessions/{session_id}/events")
    def get_events(session_id: str, after: int = 0):
        session_of(session_id)
        return {"events": [e.model_dump(mode="json") for e in st.events.since(session_id, after)]}

    @app.get("/tenants/{tenant_id}")
    def get_tenant(tenant_id: str):
        return {"tenant": lookup(ds.get_tenant, tenant_id).model_dump(mode="json"),
                "clients": [c.model_dump(mode="json") for c in lookup(ds.list_clients, tenant_id)]}

    @app.get("/tenants/{tenant_id}/approvals")
    def list_approvals(tenant_id: str, status: str = "pending"):
        if status != "pending":
            raise ApiError(400, "bad_request", "Підтримується лише status=pending")
        lookup(ds.get_tenant, tenant_id)
        return {"approvals": [a.model_dump(mode="json") for a in st.approvals.pending(tenant_id)]}

    @app.get("/tenants/{tenant_id}/metrics")
    def get_metrics(tenant_id: str):
        lookup(ds.get_tenant, tenant_id)
        return metrics(st.events, st.approvals, tenant_id)

    def finish(session: Session, approval, execute: bool) -> tuple[dict, str | None, dict | None]:
        with st.locks[session.id]:
            result = execute_approved(approval, session.ctx) if execute else {"status": "rejected"}
            try:
                return result, session.resume_after_approval(approval, result), None
            except Exception as e:
                st.events.emit(session.id, session.tenant_id, "error", {"message": str(e)})
                return result, None, {"error": "resume_failed",
                                      "message": "Дію виконано, але агент не зміг продовжити розмову."}

    @app.post("/approvals/{approval_id}/decide")
    async def decide(approval_id: str, body: Decision):
        try:
            approval = st.approvals.get(approval_id)
        except KeyError:
            raise ApiError(404, "not_found", f"Апрув {approval_id} не знайдено") from None
        session = session_of(approval.session_id)
        try:
            approval = st.approvals.decide(approval_id, body.approve, body.by, body.note)
        except ValueError:
            raise ApiError(409, "already_decided", "Апрув уже оброблено") from None
        result, reply, error = await run_in_threadpool(finish, session, approval, body.approve)
        out = {"approval": approval.model_dump(mode="json"), "result": result, "reply": reply}
        return {**out, "error": error} if error else out

    if os.path.isdir(ROOT / "web"):
        app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
    return app


app = create_app()
