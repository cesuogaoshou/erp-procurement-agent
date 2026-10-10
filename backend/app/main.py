from collections.abc import Generator

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from backend.app.db.session import create_session_factory, create_sqlite_engine
from backend.app.schemas.procurement import (
    ApprovalActionIn,
    ForecastOut,
    ForecastRequest,
    InventoryOut,
    LoginIn,
    MaterialOut,
    PurchaseDraftIn,
    PurchaseDraftOut,
    RecommendationIn,
    RecommendationOut,
    TokenOut,
)
from backend.app.services.auth import AuthError, authenticate_demo_user, issue_token, verify_token
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
from backend.app.services.recommendations import recommend_for_material


def create_app(
    engine: Engine | None = None,
    *,
    auth_secret: str = "dev-demo-secret-change-me",
    allow_header_auth: bool = False,
) -> FastAPI:
    app = FastAPI(title="ERP Intelligent Procurement Agent")
    app.state.engine = engine or create_sqlite_engine()
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.auth_secret = auth_secret
    app.state.allow_header_auth = allow_header_auth

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

    return app


def _approval_input(request: ApprovalActionIn) -> ApprovalActionInput:
    return ApprovalActionInput(
        expected_order_version=request.expected_order_version,
        idempotency_key=request.idempotency_key,
        reason=request.reason,
        body_actor_user_id=request.actor_user_id,
        body_actor_role=request.actor_role,
    )


app = create_app()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ERP procurement API module.")
    parser.add_argument("--check", action="store_true", help="Create the app and exit.")
    args = parser.parse_args()
    if args.check:
        create_app()
        print("app ok")
