"""update_ttl_idle_days

Revision ID: q2f3g4h5i6j7
Revises: p1e2f3g4h5i6
Create Date: 2026-08-29 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
import json

# revision identifiers, used by Alembic.
revision = 'q2f3g4h5i6j7'
down_revision = 'p1e2f3g4h5i6'
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    
    result = session.execute(
        sa.text("SELECT id, value FROM configs WHERE key = 'governance'")
    ).fetchone()
    
    if result:
        config_id, value_json = result
        if isinstance(value_json, str):
            value = json.loads(value_json)
        else:
            value = dict(value_json)
            
        if value.get("ttl_idle_days") != 180:
            value["ttl_idle_days"] = 180
            
            # Convert back to JSON string if needed, sqlalchemy usually handles dicts for JSON columns
            # But just to be safe with raw SQL we pass it as a JSON string
            session.execute(
                sa.text("UPDATE configs SET value = :value WHERE id = :id"),
                {"value": json.dumps(value), "id": config_id}
            )
            session.commit()

def downgrade() -> None:
    pass
