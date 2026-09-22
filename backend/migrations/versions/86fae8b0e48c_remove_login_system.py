"""remove login system

Revision ID: 86fae8b0e48c
Revises: ad4f1b5392f5
Create Date: 2026-09-22 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '86fae8b0e48c'
down_revision: Union[str, Sequence[str], None] = 'ad4f1b5392f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fk_to_users(table_name: str) -> None:
    """FK 未显式命名，MySQL 自动生成的约束名依环境而定；用 information_schema 动态查找
    而不是硬编码 `<table>_ibfk_1`，避免在约束命名不同的实例上迁移失败。"""

    bind = op.get_bind()
    inspector = inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        if fk.get("referred_table") == "users":
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")


def upgrade() -> None:
    """按用户指令移除登录系统：前端登录页、后端会话/密码校验代码已删除；本迁移收尾
    数据库结构。应用不再区分“用户”，产品选择与偏好收窄为单例全局配置。

    `users` 表从未有过真正的账户创建入口（控制台创建流程本就在本期范围外，
    `security.py` 的 `hash_password`/`generate_initial_password` 也从未被任何创建
    用户的代码路径调用），因此 `users` 表本身预期为空或至多一行；但
    `subscription_config_versions`／`user_preferences` 是真实产品数据，不能删除，
    只收窄结构。
    """

    _drop_fk_to_users("subscription_config_versions")
    op.drop_column("subscription_config_versions", "user_id")

    _drop_fk_to_users("user_preferences")
    # `user_preferences.user_id` 是当前主键；若曾经出现多个用户各自一行（设计上不应该，
    # 但表结构此前并未禁止），单例化前只保留最近更新的一行，避免下面新增的固定主键冲突。
    op.execute(
        "DELETE FROM user_preferences WHERE user_id NOT IN ("
        "SELECT user_id FROM (SELECT user_id FROM user_preferences "
        "ORDER BY updated_at DESC LIMIT 1) t)"
    )
    op.execute("ALTER TABLE user_preferences DROP PRIMARY KEY")
    op.add_column(
        "user_preferences",
        sa.Column("id", sa.Integer(), nullable=False, server_default="1"),
    )
    op.drop_column("user_preferences", "user_id")
    op.execute("ALTER TABLE user_preferences ADD PRIMARY KEY (id)")
    op.rename_table("user_preferences", "app_preferences")

    op.drop_table("users")


def downgrade() -> None:
    """重建 `users` 表结构与两张表的 `user_id` 外键；不恢复历史账户数据（本就没有真实
    创建流程），`app_preferences` 现有的单行数据在降级后归属到一个新建的占位用户。
    """

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=10), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    op.rename_table("app_preferences", "user_preferences")
    op.add_column(
        "user_preferences",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.execute("ALTER TABLE user_preferences DROP PRIMARY KEY")
    op.drop_column("user_preferences", "id")
    op.execute(
        "ALTER TABLE user_preferences MODIFY user_id INTEGER NOT NULL, "
        "ADD PRIMARY KEY (user_id)"
    )
    op.create_foreign_key(
        "user_preferences_ibfk_1", "user_preferences", "users", ["user_id"], ["id"]
    )

    op.add_column(
        "subscription_config_versions",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "subscription_config_versions_ibfk_1",
        "subscription_config_versions",
        "users",
        ["user_id"],
        ["id"],
    )
