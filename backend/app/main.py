import json
import os
from collections.abc import Callable, Generator
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.models import AgentRun, DemandHistory, Material, PurchaseOrder, ToolTrace
from backend.app.db.session import create_session_factory, create_sqlite_engine
from backend.app.schemas.procurement import (
    AgentRunIn,
    AgentRunOut,
    AgentRunSummaryOut,
    ApprovalActionIn,
    DemandHistoryPointOut,
    ForecastOut,
    ForecastRequest,
    InventoryOut,
    LoginIn,
    MaterialOut,
    PurchaseDraftIn,
    PurchaseDraftOut,
    PurchaseOrderSummaryOut,
    RecommendationIn,
    RecommendationOut,
    ToolTraceOut,
    TokenOut,
)
from backend.app.services.agent_loop import AgentLoop, AgentRunLimitExceeded
from backend.app.services.agent_provider import LLMProvider, OpenAIFunctionCallingProvider, model_from_env
from backend.app.services.auth import AuthError, auth_secret_from_env, authenticate_demo_user, issue_token, verify_token
from backend.app.services.approvals import (
    AuthContext,
    ApprovalActionInput,
    ApprovalConflict,
    ApprovalPermissionError,
    ApprovalValidationError,
    approve_order,
    reject_order,
    submit_for_approval,
)
from backend.app.services.purchase_drafts import DraftItemInput, PurchaseDraftInput, create_purchase_draft
from backend.app.services.forecasting import baseline_forecast
from backend.app.services.inventory import get_inventory_snapshot, list_materials
from backend.app.services.langgraph_runner import run_langgraph_procurement
from backend.app.services.recommendations import recommend_for_material


def create_app(
    engine: Engine | None = None,
    *,
    auth_secret: str | None = None,
    allow_header_auth: bool = False,
    agent_provider_factory: Callable[[], LLMProvider] | None = None,
) -> FastAPI:
    app = FastAPI(title="ERP Intelligent Procurement Agent")
    app.state.engine = engine or create_sqlite_engine()
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.auth_secret = auth_secret or auth_secret_from_env()
    app.state.allow_header_auth = allow_header_auth
    app.state.agent_provider_factory = agent_provider_factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_session() -> Generator[Session, None, None]:
        session = app.state.session_factory()
        try:
            yield session
        finally:
            session.close()

    def get_auth_context(
        authorization: str | None = Header(default=None, alias="Authorization"),
        user_id: str | None = Header(default=None, alias="X-User-Id"),
        role: str | None = Header(default=None, alias="X-User-Role"),
    ) -> AuthContext:
        if authorization is not None and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()
            try:
                claims = verify_token(token, secret=app.state.auth_secret)
            except AuthError as exc:
                raise HTTPException(status_code=401, detail=exc.detail) from exc
            return AuthContext(user_id=claims.user_id, role=claims.role)
        if app.state.allow_header_auth and user_id and role:
            return AuthContext(user_id=user_id, role=role)
        raise HTTPException(status_code=401, detail="authentication_required")

    def get_agent_provider() -> LLMProvider:
        if app.state.agent_provider_factory is not None:
            return app.state.agent_provider_factory()
        model = model_from_env()
        if not model:
            raise HTTPException(status_code=503, detail="llm_model_not_configured")
        return OpenAIFunctionCallingProvider(
            model=model,
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/auth/login", response_model=TokenOut)
    def login(request: LoginIn):
        try:
            claims = authenticate_demo_user(request.username, request.password)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=exc.detail) from exc
        expires_in = 3600
        token = issue_token(
            username=request.username,
            user_id=claims.user_id,
            role=claims.role,
            secret=app.state.auth_secret,
            ttl_seconds=expires_in,
        )
        return {
            "access_token": token,
            "expires_in": expires_in,
            "user_id": claims.user_id,
            "role": claims.role,
        }

    @app.get("/materials", response_model=list[MaterialOut])
    def materials(session: Session = Depends(get_session)):
        return list_materials(session)

    @app.get("/inventory/{material_id}", response_model=InventoryOut)
    def inventory(material_id: int, session: Session = Depends(get_session)):
        try:
            return get_inventory_snapshot(session, material_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/forecasts", response_model=ForecastOut)
    def forecasts(request: ForecastRequest, session: Session = Depends(get_session)):
        try:
            return baseline_forecast(session, request.material_id, request.horizon_days)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/recommendations", response_model=RecommendationOut)
    def recommendations(request: RecommendationIn, session: Session = Depends(get_session)):
        result = recommend_for_material(
            session=session,
            material_id=request.material_id,
            quantity=request.quantity,
            required_in_days=request.required_in_days,
            budget=request.budget,
        )
        return {
            "recommendations": result.recommendations,
            "excluded": result.excluded,
        }

    @app.post("/purchase-drafts", response_model=PurchaseDraftOut)
    def purchase_drafts(request: PurchaseDraftIn, session: Session = Depends(get_session)):
        try:
            order = create_purchase_draft(
                session,
                PurchaseDraftInput(
                    supplier_id=request.supplier_id,
                    items=[
                        DraftItemInput(material_id=item.material_id, quantity=item.quantity)
                        for item in request.items
                    ],
                    idempotency_key=request.idempotency_key,
                    evidence_refs=request.evidence_refs,
                ),
            )
            session.commit()
            return order
        except ValueError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/purchase-orders/{order_id}/submit", response_model=PurchaseDraftOut)
    def submit_purchase_order(
        order_id: int,
        session: Session = Depends(get_session),
        auth: AuthContext = Depends(get_auth_context),
    ):
        try:
            order = submit_for_approval(session, order_id, auth)
            session.commit()
            return order
        except ApprovalPermissionError as exc:
            session.rollback()
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ApprovalConflict as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/purchase-orders/{order_id}/approve", response_model=PurchaseDraftOut)
    def approve_purchase_order(
        order_id: int,
        request: ApprovalActionIn,
        session: Session = Depends(get_session),
        auth: AuthContext = Depends(get_auth_context),
    ):
        try:
            order = approve_order(session, order_id, auth, _approval_input(request))
            session.commit()
            return order
        except ApprovalPermissionError as exc:
            session.rollback()
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ApprovalValidationError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ApprovalConflict as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/purchase-orders/{order_id}/reject", response_model=PurchaseDraftOut)
    def reject_purchase_order(
        order_id: int,
        request: ApprovalActionIn,
        session: Session = Depends(get_session),
        auth: AuthContext = Depends(get_auth_context),
    ):
        try:
            order = reject_order(session, order_id, auth, _approval_input(request))
            session.commit()
            return order
        except ApprovalPermissionError as exc:
            session.rollback()
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ApprovalValidationError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ApprovalConflict as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/agent/runs", response_model=AgentRunOut)
    def create_agent_run(
        request: AgentRunIn,
        auth: AuthContext = Depends(get_auth_context),
        provider: LLMProvider = Depends(get_agent_provider),
    ):
        if auth.role != "buyer":
            raise HTTPException(status_code=403, detail="buyer_role_required")
        try:
            if request.use_langgraph:
                result = run_langgraph_procurement(
                    engine=app.state.engine,
                    provider=provider,
                    prompt=request.prompt,
                    thread_id=request.thread_id or f"frontend-{auth.user_id}",
                )
                return {
                    "run_id": result.get("run_id"),
                    "status": result.get("status", "unknown"),
                    "tool_calls": result.get("tool_calls", []),
                    "purchase_order_id": result.get("purchase_order_id"),
                    "error": result.get("error"),
                    "real_function_calling": result.get("real_function_calling", False),
                    "langgraph_executed": result.get("langgraph_executed", False),
                }
            result = AgentLoop(engine=app.state.engine, provider=provider).run(request.prompt)
            return {
                "run_id": result.run_id,
                "status": result.status,
                "tool_calls": result.tool_calls,
                "purchase_order_id": result.purchase_order_id,
                "total_amount": result.total_amount,
                "error": result.error,
                "real_function_calling": result.real_function_calling,
                "langgraph_executed": False,
            }
        except AgentRunLimitExceeded as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/agent/runs", response_model=list[AgentRunSummaryOut])
    def list_agent_runs(
        _auth: AuthContext = Depends(get_auth_context),
        session: Session = Depends(get_session),
    ):
        runs = session.scalars(select(AgentRun).order_by(desc(AgentRun.created_at)).limit(50)).all()
        return [_agent_run_summary(run) for run in runs]

    @app.get("/agent/runs/{run_id}", response_model=AgentRunSummaryOut)
    def get_agent_run(
        run_id: int,
        _auth: AuthContext = Depends(get_auth_context),
        session: Session = Depends(get_session),
    ):
        run = session.get(AgentRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="agent_run_not_found")
        return _agent_run_summary(run)

    @app.get("/agent/runs/{run_id}/traces", response_model=list[ToolTraceOut])
    def get_agent_run_traces(
        run_id: int,
        _auth: AuthContext = Depends(get_auth_context),
        session: Session = Depends(get_session),
    ):
        run = session.get(AgentRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="agent_run_not_found")
        traces = session.scalars(
            select(ToolTrace).where(ToolTrace.run_id == run_id).order_by(ToolTrace.step_index)
        ).all()
        return [_tool_trace_out(trace) for trace in traces]

    @app.get("/purchase-orders", response_model=list[PurchaseOrderSummaryOut])
    def list_purchase_orders(
        _auth: AuthContext = Depends(get_auth_context),
        session: Session = Depends(get_session),
    ):
        orders = session.scalars(select(PurchaseOrder).order_by(desc(PurchaseOrder.created_at)).limit(50)).all()
        return [_purchase_order_summary(order) for order in orders]

    @app.get("/demand-history/{material_id}", response_model=list[DemandHistoryPointOut])
    def demand_history(
        material_id: int,
        days: int = Query(default=120, ge=1, le=540),
        _auth: AuthContext = Depends(get_auth_context),
        session: Session = Depends(get_session),
    ):
        material = session.get(Material, material_id)
        if material is None:
            raise HTTPException(status_code=404, detail="material_not_found")
        rows = session.scalars(
            select(DemandHistory)
            .where(DemandHistory.material_id == material_id)
            .order_by(desc(DemandHistory.demand_date))
            .limit(days)
        ).all()
        return [
            {"date": row.demand_date.isoformat(), "quantity": row.quantity}
            for row in sorted(rows, key=lambda item: item.demand_date)
        ]

    return app


def _approval_input(request: ApprovalActionIn) -> ApprovalActionInput:
    return ApprovalActionInput(
        expected_order_version=request.expected_order_version,
        idempotency_key=request.idempotency_key,
        reason=request.reason,
        body_actor_user_id=request.actor_user_id,
        body_actor_role=request.actor_role,
    )


def _agent_run_summary(run: AgentRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "status": run.status,
        "prompt": run.prompt,
        "error": run.error,
        "purchase_order_id": run.purchase_order_id,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }


def _tool_trace_out(trace: ToolTrace) -> dict[str, Any]:
    return {
        "id": trace.id,
        "run_id": trace.run_id,
        "step_index": trace.step_index,
        "tool_name": trace.tool_name,
        "arguments": _loads_json(trace.arguments_json, {}),
        "output": _loads_json(trace.output_json, {}),
        "status": trace.status,
        "error": trace.error,
        "created_at": trace.created_at.isoformat(),
    }


def _purchase_order_summary(order: PurchaseOrder) -> dict[str, Any]:
    return {
        "id": order.id,
        "supplier_id": order.supplier_id,
        "supplier_name": order.supplier.name if order.supplier else "",
        "status": order.status,
        "total_amount": order.total_amount,
        "idempotency_key": order.idempotency_key,
        "version": order.version,
        "formal_order_number": order.formal_order_number,
        "evidence_refs": _loads_json(order.evidence_refs_json, []),
        "items": order.items,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }


def _loads_json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


app = create_app()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ERP procurement API module.")
    parser.add_argument("--check", action="store_true", help="Create the app and exit.")
    args = parser.parse_args()
    if args.check:
        create_app()
        print("app ok")
