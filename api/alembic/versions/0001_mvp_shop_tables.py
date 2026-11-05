"""mvp shop tables

Revision ID: 0001
Revises: 
Create Date: 2026-11-05 15:34:28.626973
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    
    op.create_table('products',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('slug', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('price', sa.BigInteger(), nullable=False),
    sa.Column('drive_url', sa.String(length=1000), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('price > 0', name=op.f('ck_products_price_positive')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_products')),
    sa.UniqueConstraint('slug', name=op.f('uq_products_slug'))
    )
    op.create_table('webhook_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('provider_event_id', sa.String(length=100), nullable=True),
    sa.Column('payload', sa.Text(), nullable=False),
    sa.Column('result', sa.String(length=50), nullable=True),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_webhook_events'))
    )
    with op.batch_alter_table('webhook_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_webhook_events_provider_event_id'), ['provider_event_id'], unique=False)

    op.create_table('orders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('product_name', sa.String(length=200), nullable=False),
    sa.Column('amount', sa.BigInteger(), nullable=False),
    sa.Column('customer_name', sa.String(length=100), nullable=False),
    sa.Column('customer_email', sa.String(length=320), nullable=False),
    sa.Column('access_token_hash', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('email_sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ip_hash', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'paid', 'expired', 'cancelled', 'needs_review')", name=op.f('ck_orders_status')),
    sa.CheckConstraint('amount > 0', name=op.f('ck_orders_amount_positive')),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_orders_product_id_products'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_orders')),
    sa.UniqueConstraint('code', name=op.f('uq_orders_code'))
    )
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_orders_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_customer_email'), ['customer_email'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_ip_hash'), ['ip_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_product_id'), ['product_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_status'), ['status'], unique=False)

    op.create_table('payment_transactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('provider_transaction_id', sa.String(length=100), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=True),
    sa.Column('amount', sa.BigInteger(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('reference_code', sa.String(length=100), nullable=True),
    sa.Column('transaction_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('note', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_payment_transactions_order_id_orders'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_transactions')),
    sa.UniqueConstraint('provider', 'provider_transaction_id', name='uq_payment_transactions_provider_tx')
    )
    with op.batch_alter_table('payment_transactions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payment_transactions_order_id'), ['order_id'], unique=False)




def downgrade() -> None:
    
    with op.batch_alter_table('payment_transactions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payment_transactions_order_id'))

    op.drop_table('payment_transactions')
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_orders_status'))
        batch_op.drop_index(batch_op.f('ix_orders_product_id'))
        batch_op.drop_index(batch_op.f('ix_orders_ip_hash'))
        batch_op.drop_index(batch_op.f('ix_orders_customer_email'))
        batch_op.drop_index(batch_op.f('ix_orders_created_at'))

    op.drop_table('orders')
    with op.batch_alter_table('webhook_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_webhook_events_provider_event_id'))

    op.drop_table('webhook_events')
    op.drop_table('products')

