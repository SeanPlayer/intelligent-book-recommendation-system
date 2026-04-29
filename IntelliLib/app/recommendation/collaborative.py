import math
from collections import defaultdict
from .utils import build_user_item_matrix, get_user_interacted_books

def cosine_similarity(vec1, vec2):
    common = set(vec1.keys()) & set(vec2.keys())
    if not common:
        return 0.0
    dot = sum(vec1[item] * vec2[item] for item in common)
    norm1 = math.sqrt(sum(v**2 for v in vec1.values()))
    norm2 = math.sqrt(sum(v**2 for v in vec2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

def find_similar_users(target_user_id, user_items, top_n=20):
    if target_user_id not in user_items:
        return []
    target_vec = user_items[target_user_id]
    similarities = []
    for other_id, other_vec in user_items.items():
        if other_id == target_user_id:
            continue
        sim = cosine_similarity(target_vec, other_vec)
        if sim > 0:
            similarities.append((other_id, sim))
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_n]

def collaborative_recommend(user_id, limit=10, exclude_ids=None):
    if exclude_ids is None:
        exclude_ids = []
    user_items = build_user_item_matrix(use_rating=True)  # 使用评分作为权重
    similar_users = find_similar_users(user_id, user_items, top_n=20)
    if not similar_users:
        return []

    interacted = get_user_interacted_books(user_id)
    exclude = interacted | set(exclude_ids)

    scores = defaultdict(float)
    for other_id, sim in similar_users:
        for book_id, weight in user_items[other_id].items():
            if book_id in exclude:
                continue
            scores[book_id] += weight * sim

    sorted_books = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    book_ids = [bid for bid, _ in sorted_books[:limit]]
    from app.models import Book
    books = Book.query.filter(Book.id.in_(book_ids)).all()
    book_dict = {b.id: b for b in books}
    return [book_dict[bid] for bid in book_ids if bid in book_dict]
