"""의미 기반 검색용 임베딩.

BM25 는 글자가 겹쳐야 찾습니다. 그래서 "해고 통보"로 물으면 "해고의 예고"(제26조)를
못 찾습니다. 통보와 예고는 뜻이 같지만 글자가 하나도 겹치지 않기 때문입니다.
"월급"과 "금품 청산", "안 돌려줘요"와 "보증금의 회수"도 마찬가지입니다.

이용자는 법전의 단어를 모릅니다. 그것이 이 서비스가 존재하는 이유이므로, 글자가
아니라 뜻으로 찾아야 합니다.

임베딩은 조문마다 한 번만 계산해 캐시에 저장하고, 질문만 그때그때 인코딩합니다.

    python tools/build_embeddings.py     # 캐시 생성 (수집 후 한 번)

sentence-transformers 가 없거나 캐시가 없으면 BM25 단독으로 조용히 되돌아갑니다.
검색 품질은 떨어지지만 서비스는 멈추지 않습니다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

import numpy as np

logger = logging.getLogger("legal_ai.embed")

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "corpus"
VECTORS_FILE = CACHE_DIR / "embeddings.npy"
META_FILE = CACHE_DIR / "embeddings.meta.json"

# 한국어 문장 임베딩 모델. 다른 모델을 쓰려면 LEGAL_AI_EMBED_MODEL 로 바꾸고
# 캐시를 다시 만드세요(모델이 다르면 벡터가 호환되지 않습니다).
DEFAULT_MODEL = os.environ.get("LEGAL_AI_EMBED_MODEL", "jhgan/ko-sroberta-multitask")

_model = None


def load_model(name: str = DEFAULT_MODEL):
    """Lazy import: sentence-transformers pulls in torch, which is heavy."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("임베딩 모델 로드: %s", name)
        _model = SentenceTransformer(name)
    return _model


def available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


def article_text(article: dict) -> str:
    """조문 제목을 앞에 두어 무엇에 관한 조문인지 신호를 줍니다."""
    title = article.get("article_title") or ""
    return f"{article['law_name']} {article.get('article_no', '')} {title}\n{article['text']}"


def corpus_fingerprint(articles: list[dict], model_name: str) -> str:
    h = hashlib.sha256()
    h.update(model_name.encode())
    h.update(str(len(articles)).encode())
    for a in articles:
        h.update(article_text(a)[:200].encode())
    return h.hexdigest()


def encode(texts: list[str], model_name: str = DEFAULT_MODEL, batch_size: int = 32) -> np.ndarray:
    model = load_model(model_name)
    vectors = model.encode(
        texts, batch_size=batch_size, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True
    )
    return vectors.astype("float32")


def build_cache(articles: list[dict], model_name: str = DEFAULT_MODEL) -> dict:
    vectors = encode([article_text(a) for a in articles], model_name)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(VECTORS_FILE, vectors)
    meta = {
        "model": model_name,
        "count": len(articles),
        "dim": int(vectors.shape[1]),
        "fingerprint": corpus_fingerprint(articles, model_name),
    }
    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def load_cache(articles: list[dict], model_name: str = DEFAULT_MODEL) -> np.ndarray | None:
    """Return cached vectors, or None if missing or stale.

    말뭉치가 바뀌었는데 옛 벡터를 쓰면 엉뚱한 조문을 반환합니다. 조용히 틀리느니
    None 을 돌려주고 BM25 로 되돌아가는 편이 낫습니다.
    """
    if not (VECTORS_FILE.exists() and META_FILE.exists()):
        return None
    try:
        meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if meta.get("fingerprint") != corpus_fingerprint(articles, model_name):
        logger.warning("임베딩 캐시가 말뭉치와 맞지 않습니다. python tools/build_embeddings.py 를 실행하세요.")
        return None
    vectors = np.load(VECTORS_FILE)
    if vectors.shape[0] != len(articles):
        return None
    return vectors


def encode_query(query: str, model_name: str = DEFAULT_MODEL) -> np.ndarray:
    return encode([query], model_name, batch_size=1)[0]
