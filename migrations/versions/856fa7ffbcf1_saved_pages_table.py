"""saved pages table

Revision ID: 856fa7ffbcf1
Revises: 49b9a36e244a
Create Date: 2022-01-13 13:26:31.446999

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '856fa7ffbcf1'
down_revision = '49b9a36e244a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('saved_page',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=True),
    sa.Column('url', sa.String(length=2048), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_saved_page_timestamp'), 'saved_page', ['timestamp'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_saved_page_timestamp'), table_name='saved_page')
    op.drop_table('saved_page')
    # ### end Alembic commands ###