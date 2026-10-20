# Legal Contract RAG: Employment Contract Analysis Tool

A prototype that compares an employment contract clause with Turkish labor law and returns a short, plain-language answer for non-lawyers.

> **Disclaimer:** This is an educational prototype. It does not provide legal advice and is for preliminary information only.

[Live demo](https://legal-contract-app-sluhkfdvzxl65jzmzqua8v.streamlit.app)

## What it does

Given a clause (or a whole contract), the app searches the uploaded laws (Labor Law No. 4857 and the Turkish Code of Obligations) and answers in exactly two sections:

1. **Concrete risk for the employee**
2. **Does it violate the law?** (Yes/No, with law name and article number)

If no retrieved article directly regulates the clause, the app returns "no relevant provision found" instead of generating an answer.

## Example

Input:

> The employee cannot claim extra pay for work beyond 45 hours per week; overtime pay is included in the salary.

Output:

[PASTE THE REAL OUTPUT FROM YOUR APP HERE]

## Architecture

```
Laws (PDF/DOCX/TXT)
   -> article-level chunking (law, article no, page metadata)
   -> embeddings (fine-tuned multilingual-e5-small)
   -> FAISS index (cached on disk)

Clause -> embedding -> top-3 articles -> relevance check + answer (Gemini) -> two-section output
```

| Component | Technology |
|---|---|
| Embedding model | `intfloat/multilingual-e5-small`, fine-tuned (`models/e5-hukuk`) |
| Vector search | FAISS (via LangChain) |
| Answer generation | Google Gemini API (generation only) |
| Document parsing | pypdf, python-docx |
| Interface | Streamlit |
| Training / evaluation | sentence-transformers, `finetune.py` |

## Fine-tuning

- **Base model:** `intfloat/multilingual-e5-small`.
- **Training data:** for each law article I wrote contract-style example sentences in three forms (violating clause, compliant clause, question). The training set has 92 query-article pairs.
- **Method:** contrastive learning with `MultipleNegativesRankingLoss`, `NO_DUPLICATES` batch sampler, `query:` / `passage:` prefixes.
- **Settings:** 4 epochs, batch size 16, learning rate 2e-5, 24 training steps in total. Trained on CPU in about 10 minutes. Training loss fell from 2.20 to 0.97 over the run.
- **Goal:** improve retrieval, i.e. finding the correct law article for a clause. The fine-tuned model does not change how Gemini phrases or judges the answer.

## Evaluation

Retrieval is evaluated with Recall@k and MRR on `eval_set.json`.

- **Eval set:** 8 clauses, each with one expected law and article. The expected articles were chosen by the author from the topic of each clause and have not been reviewed by a lawyer. Evaluation sentences were excluded from the training pairs.
- **Index:** 840 article chunks from the loaded laws.
- **Baseline:** the same model without fine-tuning, evaluated on the same set.

| Model | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|
| Baseline (`multilingual-e5-small`) | 50% (4/8) | 62% (5/8) | 62% (5/8) | 0.562 |
| Fine-tuned | 75% (6/8) | 75% (6/8) | 88% (7/8) | 0.799 |

**Limitations**

- The evaluation set is small (8 queries). One query changes Recall by 12.5 points, so these numbers show a direction, not a reliable accuracy estimate.
- The same law articles may appear in both training and evaluation (different sentences, same articles), so the improvement may be overstated.
- These results measure retrieval only. They do not show that the final answers became more accurate. Answer quality was checked manually on a few clauses and was not measured systematically.

## Run it yourself

```bash
git clone [REPO-URL]
cd legal-contract-rag
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file:

```
GEMINI_API_KEY=your_key_here
```

Start the app and upload the law files from the sidebar:

```bash
streamlit run app.py
```

**Reproduce the evaluation**

```bash
python finetune.py olc intfloat/multilingual-e5-small   # baseline
python finetune.py olc models/e5-hukuk                  # fine-tuned model
```

**Retrain**

```bash
python finetune.py hazirla   # builds data/egitim_taslak.csv; fill the query columns by hand
python finetune.py egit      # trains and saves to models/e5-hukuk
```

## Project structure

```
app.py            Streamlit app (search, answer, UI)
ingest.py         Article-level chunking and clause splitting
finetune.py       Training data preparation, training, evaluation
eval_set.json     Evaluation clauses
test_ingest.py    Offline test for chunking
data/laws/        Law files
data/sample/      Example contract (fictional)
```

## Data and privacy

- Law texts: [(https://www.mevzuat.gov.tr/MevzuatMetin/1.5.6098.pdf)]
- Example contracts in this repository are fictional. Do not upload real contracts with personal data: clause text is sent to the Gemini API for answer generation.
- `.env`, model weights and index caches are not committed.

## Known limitations

- Covers only the uploaded laws; no case law or regulations.
- Answers come from an LLM and can be wrong. Always check the cited article.
- Free API quotas can make the live demo slow or temporarily unavailable.
