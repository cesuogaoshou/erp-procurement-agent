"""Explicitly isolated V2 API; fails closed before importing the default app."""
import os
from backend.app.db.import_v2_data import validate_target

validate_target(os.environ.get('DATABASE_URL',''))

from backend.app.main import app  # noqa: E402

app.title='ERP智能采购Agent · V2自主模拟数据演示'

# Verify the actual selected database before allowing any business routes.
from backend.app.db.import_v2_data import verify_connected_target, verify_dataset_loaded
with app.state.engine.connect() as connection:
    verify_connected_target(connection)
    verify_dataset_loaded(connection)


@app.get('/environment')
def environment():
    return {'environment':'V2','dataset':'simulated_procurement_v2_20261029.1','database':'erp_procurement_demo_v2'}
