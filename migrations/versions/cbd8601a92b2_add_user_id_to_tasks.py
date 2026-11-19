
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cbd8601a92b2'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Clear existing rows that have no user_id so NOT NULL succeeds
    op.execute("DELETE FROM user_tasks")
    
    op.add_column('user_tasks', sa.Column('user_id', sa.Integer(), nullable=False))
    op.create_foreign_key(
        'fk_user_tasks_user_id_users',
        'user_tasks',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_user_tasks_user_id_users', 'user_tasks', type_='foreignkey')
    op.drop_column('user_tasks', 'user_id')