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
import re
from pathlib import Path

import numpy as np

logger = logging.getLogger("legal_ai.embed")

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "corpus"
VECTORS_FILE = CACHE_DIR / "embeddings.npy"
OWNERS_FILE = CACHE_DIR / "embeddings.owners.npy"
META_FILE = CACHE_DIR / "embeddings.meta.json"

# 조문 하나를 통째로 인코딩하면 안 됩니다.
#
# 이 저장소의 조문 중 36%가 200자를 넘고, 아동학대처벌법 제10조는 2,270자입니다.
# 임베딩 모델의 기본 입력 한도는 128토큰(한국어로 대략 200자)이라, 그 조문에서
# 실제로 "누가 신고해야 하는가"를 적어 놓은 부분은 인코딩조차 되지 않았습니다.
# 검색이 그 조문을 못 찾은 것이 당연합니다.
#
# 그래서 항(①②③) 단위로 나눠 각각을 인코딩하고, 검색할 때 같은 조문에 속한
# 조각들의 점수 중 최댓값을 그 조문의 점수로 씁니다. 질문이 조문의 어느 한 항에만
# 해당해도 찾을 수 있습니다.
MAX_SEQ_LENGTH = 512
# 한국어는 대략 2글자당 1토큰이지만 한자·괄호·법령 인용이 섞이면 더 잘게 쪼개집니다.
# 512토큰 한도에 부딪히지 않도록 여유를 두고 500자로 잡습니다.
MAX_CHUNK_CHARS = 500
HANG_MARKER = re.compile(r"(?=[①-⑳])")  # ① ~ ⑳

# 임베딩 모델.
#
# 처음에 고른 jhgan/ko-sroberta-multitask 는 **문장 유사도(STS)** 모델이었습니다.
# 두 문장이 얼마나 비슷한지를 재도록 학습된 모델이라, 길이와 성격이 같은 문장끼리
# 비교하는 데 강합니다. 그런데 우리가 하는 일은 다릅니다. "남편이 때렸어요" 라는
# 짧은 구어체 질문으로 수백 자짜리 법조문을 찾아야 합니다. 질문과 문서가 길이도
# 문체도 전혀 다른 **비대칭 검색**이고, STS 모델은 여기에 맞게 학습되지 않았습니다.
#
# multilingual-e5 와 bge-m3 는 정확히 이 비대칭 검색을 위해 학습된 모델입니다.
# e5 계열은 질문에 "query: ", 문서에 "passage: " 접두어를 붙여야 제 성능이 납니다.
#
# 모델을 바꾸면 벡터가 호환되지 않으므로 캐시를 반드시 다시 만들어야 합니다.
DEFAULT_MODEL = os.environ.get("LEGAL_AI_EMBED_MODEL", "intfloat/multilingual-e5-large")


def _prefixes(model_name: str) -> tuple[str, str]:
    """(질문 접두어, 문서 접두어). e5 계열은 접두어가 없으면 성능이 크게 떨어집니다."""
    if "e5" in model_name.lower():
        return "query: ", "passage: "
    return "", ""

_model = None


def load_model(name: str = DEFAULT_MODEL):
    """Lazy import: sentence-transformers pulls in torch, which is heavy."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("임베딩 모델 로드: %s", name)
        _model = SentenceTransformer(name)
        # 기본값 128 은 법령 조문에 턱없이 짧습니다. 청킹과 함께 올려 둡니다.
        _model.max_seq_length = min(MAX_SEQ_LENGTH, getattr(_model, "max_seq_length", 512) or 512)
        _model.max_seq_length = MAX_SEQ_LENGTH
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


def chunk_article(article: dict) -> list[str]:
    """조문을 항 단위로 나눕니다. 모든 조각에 법령명과 조문 제목을 붙여,
    조각만 봐도 어느 법 어느 조문인지 알 수 있게 합니다."""
    header = f"{article['law_name']} {article.get('article_no', '')} {article.get('article_title') or ''}".strip()
    body = article["text"].strip()

    parts = [p.strip() for p in HANG_MARKER.split(body) if p.strip()]
    chunks: list[str] = []
    buffer = ""
    for part in parts:
        # 너무 긴 항은 다시 문장 단위로 자릅니다. 자르기 전에 쌓아 둔 버퍼를 먼저
        # 내보내야 조각 순서가 원문 순서와 같아집니다.
        if len(part) > MAX_CHUNK_CHARS and buffer:
            chunks.append(buffer)
            buffer = ""
        while len(part) > MAX_CHUNK_CHARS:
            cut = part.rfind(". ", 0, MAX_CHUNK_CHARS)
            cut = cut + 1 if cut > MAX_CHUNK_CHARS // 2 else MAX_CHUNK_CHARS
            chunks.append(part[:cut].strip())
            part = part[cut:].strip()
        if len(buffer) + len(part) + 1 <= MAX_CHUNK_CHARS:
            buffer = f"{buffer} {part}".strip()
        else:
            if buffer:
                chunks.append(buffer)
            buffer = part
    if buffer:
        chunks.append(buffer)

    return [f"{header}\n{c}" for c in (chunks or [body])]


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
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        # 질문 한 건을 인코딩할 때마다 진행 막대가 뜨면 화면이 그것으로 덮여
        # 정작 봐야 할 평가 결과가 묻힙니다. 대량 인코딩일 때만 표시합니다.
        show_progress_bar=len(texts) > 16,
    )
    return vectors.astype("float32")


def build_cache(articles: list[dict], model_name: str = DEFAULT_MODEL) -> dict:
    texts: list[str] = []
    owners: list[int] = []
    for i, article in enumerate(articles):
        for chunk in chunk_article(article):
            texts.append(chunk)
            owners.append(i)

    _, passage_prefix = _prefixes(model_name)
    vectors = encode([passage_prefix + t for t in texts], model_name)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(VECTORS_FILE, vectors)
    np.save(OWNERS_FILE, np.asarray(owners, dtype="int32"))
    meta = {
        "model": model_name,
        "articles": len(articles),
        "chunks": len(texts),
        "dim": int(vectors.shape[1]),
        "max_seq_length": MAX_SEQ_LENGTH,
        "fingerprint": corpus_fingerprint(articles, model_name),
    }
    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def load_cache(
    articles: list[dict], model_name: str = DEFAULT_MODEL
) -> tuple[np.ndarray, np.ndarray] | None:
    """(벡터, 소유 조문 인덱스) 또는 None.

    말뭉치가 바뀌었는데 옛 벡터를 쓰면 엉뚱한 조문을 반환합니다. 조용히 틀리느니
    None 을 돌려주고 BM25 로 되돌아가는 편이 낫습니다.
    """
    if not (VECTORS_FILE.exists() and OWNERS_FILE.exists() and META_FILE.exists()):
        return None
    try:
        meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if meta.get("fingerprint") != corpus_fingerprint(articles, model_name):
        logger.warning("임베딩 캐시가 말뭉치와 맞지 않습니다. python tools/build_embeddings.py 를 실행하세요.")
        return None
    vectors = np.load(VECTORS_FILE)
    owners = np.load(OWNERS_FILE)
    if vectors.shape[0] != owners.shape[0] or int(owners.max(initial=-1)) >= len(articles):
        return None
    return vectors, owners


def encode_query(query: str, model_name: str = DEFAULT_MODEL) -> np.ndarray:
    query_prefix, _ = _prefixes(model_name)
    return encode([query_prefix + query], model_name, batch_size=1)[0]
