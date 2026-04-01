import streamlit as st
import ollama
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer, CrossEncoder
import faiss
import numpy as np
import time
import psutil
import os
import pickle
from datetime import datetime
import glob
import pandas as pd
from rank_bm25 import BM25Okapi

# ================= CONFIG =================
PDF_FOLDER_PATH = r"C:\Users\Desktop\Input"   
QUESTIONS_FILE = "questions.txt"
INDEX_FILE = "faiss_index.idx"
CHUNKS_FILE = "chunks.pkl"
CSV_OUTPUT_FILE = "benchmark_results.csv"

st.set_page_config(page_title="RAG Benchmark v4", layout="wide")
st.title("RAG Benchmark v4")

# ================= SIDEBAR =================
st.sidebar.header("Settings")
models = ["llama3.2:3b", "gemma2:2b", "phi3:mini", "qwen2.5:3b"]
selected_model = st.sidebar.selectbox("Ollama Model", models, index=0)

chunk_size = st.sidebar.slider("Chunk Size (chars)", 200, 2000, 700, step=100)
k_value = st.sidebar.slider("Retrieved Chunks (k) before rerank", 2, 50, 25)

embedding_options = {
    "all-MiniLM-L6-v2 (Fast)": "all-MiniLM-L6-v2",
    "nomic-embed-text-v1.5 (Better)": "nomic-ai/nomic-embed-text-v1.5",
    "bge-small-en-v1.5 (Strong)": "BAAI/bge-small-en-v1.5"
}
selected_embed = st.sidebar.selectbox("Embedding Model", list(embedding_options.keys()))
embedder_name = embedding_options[selected_embed]

index_type = st.sidebar.radio("FAISS Index Type", ["FlatL2 (Exact)", "IVFFlat (Balanced)", "HNSW (Fastest)"])

reindex = st.sidebar.button("Force Re-Index All PDFs", type="primary")
run_auto = st.sidebar.button("Run Automated 10-Question Benchmark", type="primary")

# ================= SESSION STATE =================
if "index" not in st.session_state: st.session_state.index = None
if "chunks" not in st.session_state: st.session_state.chunks = None
if "embedder" not in st.session_state: st.session_state.embedder = None
if "auto_results" not in st.session_state: st.session_state.auto_results = []
if "index_loaded" not in st.session_state: st.session_state.index_loaded = False

# ================= LOAD SAVED INDEX =================
if not reindex and not st.session_state.index_loaded:
    if os.path.exists(INDEX_FILE) and os.path.exists(CHUNKS_FILE):
        try:
            st.session_state.index = faiss.read_index(INDEX_FILE)
            with open(CHUNKS_FILE, "rb") as f:
                st.session_state.chunks = pickle.load(f)
            st.session_state.embedder = SentenceTransformer(embedder_name, trust_remote_code=True)
            st.session_state.index_loaded = True
            st.success("Loaded existing FAISS index from disk — ready for benchmark")
        except Exception as e:
            st.warning(f"Failed to load index: {e}")

# ================= BM25 + VECTOR HYBRID + RERANKER =================
@st.cache_resource
def load_reranker():
    return CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', device='cpu')

reranker = load_reranker()

def hybrid_retrieve(chunks, query, k=25):
    # Step 1: BM25 keyword search
    common = {"what", "the", "for", "and", "per", "date", "all", "years", "is", "in", "on", "to", "of", "with", "by"}
    keywords = [word.lower() for word in query.split() if len(word) > 3 and word.lower() not in common]
    
    tokenized_chunks = [chunk.lower().split() for chunk in chunks]
    bm25 = BM25Okapi(tokenized_chunks)
    bm25_scores = bm25.get_scores(keywords)
    
    # Get top BM25 candidates
    bm25_top_idx = np.argsort(bm25_scores)[::-1][:k*2]
    bm25_candidates = [chunks[i] for i in bm25_top_idx]

    # Step 2: Vector search
    q_emb = st.session_state.embedder.encode([query])[0].astype('float32')
    D, I = st.session_state.index.search(np.array([q_emb]), k=k*2)
    vector_candidates = [chunks[i] for i in I[0]]

    # Step 3: Combine and remove duplicates
    combined = list(dict.fromkeys(bm25_candidates + vector_candidates))

    # Step 4: Rerank with cross-encoder
    final_chunks = rerank_chunks(query, combined[:30], top_n=6)
    return final_chunks

def rerank_chunks(query, candidate_chunks, top_n=6):
    if not candidate_chunks:
        return []
    pairs = [[query, chunk] for chunk in candidate_chunks]
    scores = reranker.predict(pairs)
    sorted_idx = np.argsort(scores)[::-1]
    return [candidate_chunks[i] for i in sorted_idx[:top_n]]

# ================= AUTO INDEXING =================
if reindex or st.session_state.index is None:
    pdf_files = glob.glob(os.path.join(PDF_FOLDER_PATH, "*.pdf"))
    if not pdf_files:
        st.error(f"No PDFs found in: {PDF_FOLDER_PATH}")
        st.stop()

    start_time = time.time()
    process = psutil.Process()
    ram_before = process.memory_info().rss / (1024 ** 2)

    with st.spinner(f"Indexing {len(pdf_files)} PDFs..."):
        full_text = ""
        for file_path in pdf_files:
            reader = PdfReader(file_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        chunks = [c.strip() for c in chunks if c.strip()]

        embedder = SentenceTransformer(embedder_name, trust_remote_code=True)
        embeddings = embedder.encode(chunks, show_progress_bar=True)
        embeddings = np.array(embeddings).astype('float32')

        dim = embeddings.shape[1]
        if index_type == "FlatL2 (Exact)":
            index = faiss.IndexFlatL2(dim)
        elif index_type == "IVFFlat (Balanced)":
            nlist = min(100, len(chunks) // 50 or 1)
            quantizer = faiss.IndexFlatL2(dim)
            index = faiss.IndexIVFFlat(quantizer, dim, nlist)
            index.train(embeddings)
        else:
            index = faiss.IndexHNSWFlat(dim, 32)
            index.hnsw.efConstruction = 200

        index.add(embeddings)

        # Save index
        faiss.write_index(index, INDEX_FILE)
        with open(CHUNKS_FILE, "wb") as f:
            pickle.dump(chunks, f)

        st.session_state.index = index
        st.session_state.chunks = chunks
        st.session_state.embedder = embedder
        st.session_state.index_loaded = True

        indexing_time = time.time() - start_time
        ram_used = process.memory_info().rss / (1024 ** 2) - ram_before

        st.success(f"Indexed {len(chunks):,} chunks in {indexing_time:.1f}s | RAM +{ram_used:.1f} MB | Saved to disk")

# ================= FULLY AUTOMATIC BENCHMARK WITH DEBUG =================
if run_auto:
    if st.session_state.index is None:
        st.error("Please index PDFs first!")
        st.stop()

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip()]

    if len(questions) == 0:
        st.error("No questions found in questions.txt")
        st.stop()

    st.session_state.auto_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, q in enumerate(questions):
        status_text.text(f"Processing Q{i+1}/{len(questions)}: {q[:80]}...")

        query_start = time.time()

        final_chunks = hybrid_retrieve(st.session_state.chunks, q, k=25)
        context = "\n\n".join(final_chunks)

        # ================= DEBUG OUTPUT =================
        st.write(f"**Debug - Top retrieved chunks for Q{i+1}:**")
        for idx, chunk in enumerate(final_chunks[:3]):   # show first 3 for debugging
            st.write(f"Chunk {idx+1}: {chunk[:300]}...")

        full_prompt = f"""Use only the following context to answer. If unsure, say "Not found in documents".

Context:
{context}

Question: {q}
Answer:"""

        response = ollama.generate(model=selected_model, prompt=full_prompt)["response"]
        latency = time.time() - query_start

        st.session_state.auto_results.append({
            "Question #": i+1,
            "Question": q,
            "Answer": response,
            "Latency (seconds)": round(latency, 2)
        })

        st.write(f"**Q{i+1}:** {q}")
        st.write(response)
        st.caption(f"⏱ This response: {latency/60:.2f} min ({latency:.2f}s)")

        progress_bar.progress((i+1)/len(questions))
        time.sleep(1)

    st.success("Benchmark completed!")
    df = pd.DataFrame(st.session_state.auto_results)
    avg = df["Latency (seconds)"].mean()
    df["Avg Latency (s)"] = round(avg, 2)
    df.to_csv(CSV_OUTPUT_FILE, index=False)
    st.success(f"Results saved to {CSV_OUTPUT_FILE}")
    st.write(f"**Final Average Latency:** {avg:.2f} seconds ({avg/60:.2f} minutes)")
    st.dataframe(df, use_container_width=True)