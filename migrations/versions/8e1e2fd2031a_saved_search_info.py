"""saved search info

Revision ID: 8e1e2fd2031a
Revises: 856fa7ffbcf1
Create Date: 2022-06-10 16:24:18.866267

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e1e2fd2031a'
down_revision = '856fa7ffbcf1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('saved_page', sa.Column('search_results', sa.PickleType(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('saved_page', 'search_results')
    # ### end Alembic commands ###