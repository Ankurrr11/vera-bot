import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def retrieve_relevant_digest_items(query: str, digest_items: list, top_k: int = 2) -> list:
    """
    Retrieve the most relevant digest items for a given query (trigger payload).
    Uses TF-IDF and cosine similarity for fast, lightweight matching.
    """
    if not digest_items:
        return []
        
    if len(digest_items) <= top_k:
        return digest_items

    # Extract text from digest items for vectorization
    documents = []
    for item in digest_items:
        if isinstance(item, str):
            documents.append(item)
        elif isinstance(item, dict):
            # Try to grab title and description if available
            text = f"{item.get('title', '')} {item.get('description', '')} {item.get('content', '')}".strip()
            if not text:
                text = json.dumps(item)
            documents.append(text)
        else:
            documents.append(str(item))

    # Add the query to the documents list
    all_texts = [query] + documents

    try:
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        
        # Calculate cosine similarity between query (index 0) and all documents (index 1 onwards)
        cosine_similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        
        # Get indices of top_k most similar documents
        top_indices = cosine_similarities.argsort()[-top_k:][::-1]
        
        results = [digest_items[i] for i in top_indices if cosine_similarities[i] > 0]
        if not results:
            return digest_items[:top_k]
        return results
    except Exception as e:
        # Fallback to returning the first top_k items if vectorization fails
        print(f"RAG Error: {e}")
        return digest_items[:top_k]
