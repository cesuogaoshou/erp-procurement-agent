from collections.abc import Generator

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from backend.app.db.session import create_session_factory, create_sqlite_engine
from backend.app.schemas.procurement import (
    ForecastOut,
    ForecastRequest,
    InventoryOut,
    MaterialOut,
    PurchaseDraftIn,
    PurchaseDraftOut,
    RecommendationIn,
    RecommendationOut,
)
from backend.app.services.purchase_drafts import DraftItemInput, PurchaseDraftInput, create_purchase_draft
from backend.app.services.forecasting import baseline_forecast
from backend.app.services.inventory import get_inventory_snapshot, list_materials
from backend.app.services.recommendations import recommend_for_material


def create_app(engine: Engine | None = None) -> FastAPI:
    app = FastAPI(title="ERP Intelligent Procurement Agent")
    app.state.engine = engine or create_sqlite_engine()
    app.state.session_factory = create_session_factory(app.state.engine)

    def get_session() -> Generator[Session, None, None]:
        session = app.state.session_factory()
        try:
            yield session
        finally:
            session.close()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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

    return app


app = create_app()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ERP procurement API module.")
    parser.add_argument("--check", action="store_true", help="Create the app and exit.")
    args = parser.parse_args()
    if args.check:
        create_app()
        print("app ok")
