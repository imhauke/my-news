from app.schemas import CommentNode


def build_tree(rows: list[dict]) -> list[CommentNode]:
    """Reconstruye el árbol desde filas planas en preorden (como las devuelve la consulta recursiva)."""
    roots: list[CommentNode] = []
    stack: list[CommentNode] = []
    for row in rows:
        node = CommentNode(**row)
        while stack and stack[-1].depth >= node.depth:
            stack.pop()
        (stack[-1].children if stack else roots).append(node)
        stack.append(node)
    return roots
