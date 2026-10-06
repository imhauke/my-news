"""Hacker News threads: comments are stored flat and read back in reading order with a recursive
query; the tree is rebuilt from that order."""

from sqlalchemy import text

from app.schemas import CommentNode

COMMENTS_SQL = text("""
    WITH RECURSIVE tree AS (
        SELECT id, author, text, text_es, created_at, depth, ARRAY[sibling_rank] AS path
        FROM hn_comments WHERE story_id = :story AND parent_id = :story AND NOT deleted
        UNION ALL
        SELECT c.id, c.author, c.text, c.text_es, c.created_at, c.depth, t.path || c.sibling_rank
        FROM hn_comments c JOIN tree t ON c.parent_id = t.id WHERE NOT c.deleted
    )
    SELECT id, author, text, text_es, created_at, depth FROM tree ORDER BY path
""")


def build_tree(rows: list[dict]) -> list[CommentNode]:
    """Rebuilds the tree from flat pre-order rows (as returned by the recursive query)."""
    roots: list[CommentNode] = []
    stack: list[CommentNode] = []
    for row in rows:
        node = CommentNode(**row)
        while stack and stack[-1].depth >= node.depth:
            stack.pop()
        (stack[-1].children if stack else roots).append(node)
        stack.append(node)
    return roots
