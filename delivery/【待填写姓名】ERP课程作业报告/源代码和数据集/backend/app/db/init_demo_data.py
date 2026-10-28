import argparse
from pathlib import PurePosixPath
from urllib.parse import urlparse

from sqlalchemy import create_engine, delete, func, select

from backend.app.config import load_project_env
from backend.app.models import (
    ApprovalRecord,
    AgentRun,
    AuditLog,
    DemandHistory,
    Inventory,
    Material,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierMaterial,
    SupplierPerformance,
    ToolTrace,
)
from backend.app.models.base import Base
from backend.app.services.seed import DEMO_SEED, seed_demo_data


def validate_demo_database_url(database_url: str) -> None:
    parsed = urlparse(database_url)
    if parsed.scheme.startswith("sqlite"):
        database_name = PurePosixPath(parsed.path).name
    else:
        database_name = parsed.path.lstrip("/").split("/", 1)[0]
    if "demo" not in database_name.lower():
        raise ValueError("demo_database_required")


def initialize_demo_database(database_url: str, seed: int = DEMO_SEED) -> dict[str, int]:
    validate_demo_database_url(database_url)
    engine = create_engine(database_url)
    if database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)
    with engine.begin() as connection:
        for table in [
            ToolTrace,
            AgentRun,
            AuditLog,
            ApprovalRecord,
            PurchaseOrderItem,
            PurchaseOrder,
            SupplierPerformance,
            SupplierMaterial,
            DemandHistory,
            Inventory,
            Supplier,
            Material,
        ]:
            connection.execute(delete(table))

    from backend.app.db.session import create_session_factory

    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_demo_data(session, seed=seed)
        session.commit()
        counts = {
            "materials": session.scalar(select(func.count()).select_from(Material)),
            "inventory": session.scalar(select(func.count()).select_from(Inventory)),
            "demand_history": session.scalar(select(func.count()).select_from(DemandHistory)),
            "suppliers": session.scalar(select(func.count()).select_from(Supplier)),
            "supplier_materials": session.scalar(select(func.count()).select_from(SupplierMaterial)),
            "supplier_performance": session.scalar(select(func.count()).select_from(SupplierPerformance)),
            "purchase_orders": session.scalar(select(func.count()).select_from(PurchaseOrder)),
        }
    engine.dispose()
    return counts


def main() -> None:
    load_project_env()
    parser = argparse.ArgumentParser(description="Initialize deterministic demo procurement data.")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--seed", type=int, default=DEMO_SEED)
    args = parser.parse_args()
    try:
        counts = initialize_demo_database(args.database_url, seed=args.seed)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(counts)


if __name__ == "__main__":
    main()
