import argparse
import os

from sqlalchemy import create_engine, delete, func, select

from backend.app.models import (
    ApprovalRecord,
    AuditLog,
    DemandHistory,
    Inventory,
    Material,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierMaterial,
    SupplierPerformance,
)
from backend.app.services.seed import DEMO_SEED, seed_demo_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize deterministic demo procurement data.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--seed", type=int, default=DEMO_SEED)
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL or --database-url is required")

    engine = create_engine(args.database_url)
    with engine.begin() as connection:
        for table in [
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
        seed_demo_data(session, seed=args.seed)
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
    print(counts)


if __name__ == "__main__":
    main()
