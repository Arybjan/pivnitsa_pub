
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = '003b733b24fc'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('bookings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('table_id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('guests', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'CONFIRMED', 'CANCELLED', 'EXPIRED', name='bookingstatus'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )



def downgrade() -> None:

    op.drop_table('bookings')

