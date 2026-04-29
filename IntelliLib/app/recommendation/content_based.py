"""
基于内容的过滤
"""
import math
from collections import Counter
from app.models import User, Book, BorrowRecord

CATEGORY_MAP = {
    'computer_science': '计算机科学',
    'software_engineering': '软件工程',
    'artificial_intelligence': '人工智能',
    'data_science': '数据科学',
    'web_development': 'Web开发',
    'fiction': '文学小说',
    'history': '历史传记',
    'economics': '经济管理',
    'science': '自然科学',
    'other': '其他'
}


class ContentBasedRecommender:
    def __init__(self):
        self.book_vectors = None
        self.book_ids = None
        self.idf = None
        self.term_index = None
        self.all_terms = None

    def _build_term_lists(self):
        """构建所有图书的标签列表，并建立词表"""
        books = Book.query.filter_by(status='active').all()
        self.book_ids = [b.id for b in books]
        doc_terms = []
        all_terms_set = set()
        for book in books:
            if book.tags:
                terms = [t.strip() for t in book.tags.split(',') if t.strip()]
            else:
                terms = []
            doc_terms.append(terms)
            all_terms_set.update(terms)
        self.all_terms = sorted(all_terms_set)
        self.term_index = {t: i for i, t in enumerate(self.all_terms)}
        return doc_terms

    def _compute_tfidf(self, doc_terms):
        """计算TF-IDF向量"""
        n_docs = len(doc_terms)
        df = Counter()
        for terms in doc_terms:
            df.update(set(terms))
        self.idf = {}
        for term, freq in df.items():
            self.idf[term] = math.log((n_docs + 1) / (freq + 1)) + 1
        vectors = []
        for terms in doc_terms:
            vec = [0.0] * len(self.all_terms)
            tf = Counter(terms)
            max_tf = max(tf.values()) if tf else 1
            for term, freq in tf.items():
                idx = self.term_index[term]
                vec[idx] = (freq / max_tf) * self.idf[term]
            vectors.append(vec)
        return vectors

    def train(self):
        """训练：计算所有图书的TF-IDF向量"""
        doc_terms = self._build_term_lists()
        self.book_vectors = self._compute_tfidf(doc_terms)

    def _get_user_interest_tags(self, user):
        """获取用户的兴趣标签集合（用于构建用户向量）"""
        tags = set()
        if user.interest_tags:
            tags.update([t.strip() for t in user.interest_tags.split(',') if t.strip()])
        # 从借阅历史中提取图书标签（最近10本，取所有标签）
        for record in user.borrow_records.order_by(BorrowRecord.borrow_date.desc()).limit(10):
            if record.book and record.book.tags:
                tags.update([t.strip() for t in record.book.tags.split(',') if t.strip()])
        return tags

    def _user_vector(self, user):
        """构建用户向量：基于兴趣标签，权重使用idf"""
        vec = [0.0] * len(self.all_terms)
        tags = self._get_user_interest_tags(user)
        if not tags:
            return vec
        for tag in tags:
            if tag in self.term_index:
                idx = self.term_index[tag]
                vec[idx] += self.idf.get(tag, 1.0)
        # 归一化
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def _cosine_sim(self, vec1, vec2):
        dot = sum(v1 * v2 for v1, v2 in zip(vec1, vec2))
        norm1 = math.sqrt(sum(v * v for v in vec1))
        norm2 = math.sqrt(sum(v * v for v in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def recommend(self, user_id, limit=10, exclude_ids=None):
        if exclude_ids is None:
            exclude_ids = []
        user = User.query.get(user_id)
        if not user:
            return []
        if self.book_vectors is None:
            self.train()
        user_vec = self._user_vector(user)
        if sum(user_vec) == 0:
            from .popularity import get_hot_books
            return get_hot_books(limit, exclude_ids)
        # 排除列表由调用方提供（评估时传入训练集书，在线时传入用户已借阅的所有书）
        exclude = set(exclude_ids)
        scores = []
        for idx, bid in enumerate(self.book_ids):
            if bid in exclude:
                continue
            book_vec = self.book_vectors[idx]
            sim = self._cosine_sim(user_vec, book_vec)
            if sim > 0:
                scores.append((bid, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        rec_ids = [bid for bid, _ in scores[:limit]]
        if len(rec_ids) < limit:
            from .popularity import get_hot_books
            hot = get_hot_books(limit - len(rec_ids), exclude_ids)
            rec_ids.extend([b.id for b in hot if b.id not in rec_ids])
        books = Book.query.filter(Book.id.in_(rec_ids)).all()
        book_dict = {b.id: b for b in books}
        return [book_dict[bid] for bid in rec_ids if bid in book_dict]


# 单例
_content_instance = None


def get_content_based():
    global _content_instance
    if _content_instance is None:
        _content_instance = ContentBasedRecommender()
        _content_instance.train()
    return _content_instance


def content_based_recommend(user_id, limit=10, exclude_ids=None, **kwargs):
    cb = get_content_based()
    return cb.recommend(user_id, limit, exclude_ids)

def similar_books(book_id, limit=6):
    """基于内容推荐相似图书"""
    cb = get_content_based()
    if not cb.book_ids or book_id not in cb.book_ids:
        return []
    # 获取目标图书的索引和向量
    idx = cb.book_ids.index(book_id)
    target_vec = cb.book_vectors[idx]
    scores = []
    for i, other_id in enumerate(cb.book_ids):
        if i == idx:
            continue
        other_vec = cb.book_vectors[i]
        sim = cb._cosine_sim(target_vec, other_vec)
        if sim > 0:
            scores.append((other_id, sim))
    scores.sort(key=lambda x: x[1], reverse=True)
    rec_ids = [bid for bid, _ in scores[:limit]]
    books = Book.query.filter(Book.id.in_(rec_ids)).all()
    # 添加分类显示名
    for book in books:
        book.category_display = CATEGORY_MAP.get(book.category, book.category)
    return books