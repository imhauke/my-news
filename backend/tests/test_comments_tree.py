from datetime import UTC, datetime

from app.api.comments_tree import build_tree

NOW = datetime(2026, 10, 5, tzinfo=UTC)


def row(id, depth):
    return dict(id=id, author="a", text="t", created_at=NOW, depth=depth)


def test_build_tree_from_preorder_rows():
    tree = build_tree([row(1, 0), row(2, 1), row(3, 2), row(4, 1), row(5, 0)])
    assert [n.id for n in tree] == [1, 5]
    assert [c.id for c in tree[0].children] == [2, 4]
    assert [c.id for c in tree[0].children[0].children] == [3]
