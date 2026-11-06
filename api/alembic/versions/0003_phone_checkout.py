"""phone checkout + list price: orders.customer_phone, name/email optional, products.list_price

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-06 21:21:48.116632
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('list_price', sa.BigInteger(), nullable=True))

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_phone', sa.String(length=15), nullable=True))
        batch_op.alter_column('customer_name',
               existing_type=sa.VARCHAR(length=100),
               nullable=True)
        batch_op.alter_column('customer_email',
               existing_type=sa.VARCHAR(length=320),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_orders_customer_phone'), ['customer_phone'], unique=False)




def downgrade() -> None:
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('list_price')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_orders_customer_phone'))
        batch_op.alter_column('customer_email',
               existing_type=sa.VARCHAR(length=320),
               nullable=False)
        batch_op.alter_column('customer_name',
               existing_type=sa.VARCHAR(length=100),
               nullable=False)
        batch_op.drop_column('customer_phone')


