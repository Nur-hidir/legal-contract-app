# Legal Contract RAG: Employment Contract Analysis Tool

A prototype that compares an employment contract clause with Turkish labor law and returns a short, plain-language answer for non-lawyers.

> **Status:** Work in progress. This is a prototype I plan to keep improving.

> **Disclaimer:** This is an educational prototype. It does not provide legal advice and is for preliminary information only.

[Live demo](https://legal-contract-app-sluhkfdvzxl65jzmzqua8v.streamlit.app)

## What it does

Given a clause (or a whole contract), the app searches the uploaded laws (Labor Law No. 4857 and the Turkish Code of Obligations) and answers in exactly two sections:

1. **Concrete risk for the employee**
2. **Does it violate the law?** (Yes/No, with law name and article number)

If no retrieved article directly regulates the clause, the app returns "no relevant provision found" instead of generating an answer.

In addition, a small rule-based layer (no AI) checks a few clear-cut cases and shows the result in a separate "Kural kontrolü" box.

In full-contract mode the app splits an uploaded contract into numbered clauses, analyzes each one and shows a summary: likely violating, needs attention, looks fine, no relevant provision found.

## Example

Input (the app works with Turkish contracts):

> Çalışan, haftalık 45 saati aşan çalışmaları için ayrıca ücret talep edemez; fazla mesai ücreti maaşa dahildir ve ek bir ödeme yapılmaz.
>
> (The employee cannot claim extra pay for work beyond 45 hours per week; overtime pay is included in the salary and no additional payment is made.)

Output, as returned by the app:

> **Kural kontrolü: Kanuna aykırı (4857 sayılı İş Kanunu, Madde 41)**
> Haftada 45 saati aşan her çalışma saati için normal ücretin %50 fazlası ödenmelidir. Bu hak sözleşmeyle kaldırılamaz.
>
> **1. Çalışan İçin Somut Risk:**
> Haftada 45 saatten fazla çalıştığında ek ücret alamaz; bu durum çalışanın gelirini düşürür ve yasal haklarından mahrum bırakır.
>
> **2. Kanuna Aykırı Mı?:**
> Evet – 4857 sayılı İş Kanunu, Madde 41'de fazla çalışma için normal ücretin %50 artırılmış ödenmesini şart koşar.

## Architecture

```
Laws (PDF/DOCX/TXT)
   -> article-level chunking (law, article no, page metadata)
   -> embeddings (fine-tuned multilingual-e5-small)
   -> FAISS index (cached on disk)

Clause -> rule-based checks (rules.py)
       -> embedding -> top-3 articles -> relevance check + answer (LLM) -> two-section output
```

| Component | Technology |
|---|---|
| Embedding model | `intfloat/multilingual-e5-small`, fine-tuned (`models/e5-hukuk`) |
| Vector search | FAISS (via LangChain) |
| Answer generation | Groq API, `openai/gpt-oss-120b` (generation only) |
| Rule-based checks | `rules.py`: deterministic checks, no AI |
| Document parsing | pypdf, python-docx |
| Interface | Streamlit |
| Training / evaluation | sentence-transformers, `finetune.py` |

## Rule-based checks

`rules.py` checks four clear-cut topics with keyword and number matching:

| Topic | Law | What it flags |
|---|---|---|
| Notice period | Labor Law No. 4857, Art. 17 | Notice shorter than 2 weeks (violation); shorter than 8 weeks (warning, depends on seniority) |
| Overtime pay | Labor Law No. 4857, Art. 41 | Clauses that exclude extra pay for overtime |
| Annual leave | Labor Law No. 4857, Art. 53 | Clauses that remove the right to annual paid leave |
| Non-compete duration | Code of Obligations, Art. 445 | Post-employment non-compete longer than 2 years |

These checks are keyword-based. They can miss differently worded clauses. Run `python test_rules.py` to see the test cases.

## Fine-tuning

- **Base model:** `intfloat/multilingual-e5-small`.
- **Training data:** for each law article I wrote contract-style example sentences in three forms (violating clause, compliant clause, question). The training set has 92 query-article pairs.
- **Method:** contrastive learning with `MultipleNegativesRankingLoss`, `NO_DUPLICATES` batch sampler, `query:` / `passage:` prefixes.
- **Settings:** 4 epochs, batch size 16, learning rate 2e-5, 24 training steps in total. Trained on CPU in about 10 minutes. Training loss fell from 2.20 to 0.97 over the run.
- **Goal:** improve retrieval, i.e. finding the correct law article for a clause. The fine-tuned model does not change how the LLM phrases or judges the answer.

## Evaluation

Retrieval is evaluated with Recall@k and MRR on `eval_set.json`.

- **Eval set:** 8 clauses, each with one expected law and article. The expected articles were chosen by the author from the topic of each clause and have not been reviewed by a lawyer. Evaluation sentences were excluded from the training pairs.
- **Index:** 840 article chunks from the loaded laws.
- **Baseline:** the same model without fine-tuning, evaluated on the same set.

| Model | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|
| Baseline (`multilingual-e5-small`) | 50% (4/8) | 62% (5/8) | 62% (5/8) | 0.562 |
| Fine-tuned | 75% (6/8) | 75% (6/8) | 88% (7/8) | 0.799 |

**Limitations of this evaluation**

- The evaluation set is small (8 queries). One query changes Recall by 12.5 points, so these numbers show a direction, not a reliable accuracy estimate.
- The same law articles may appear in both training and evaluation (different sentences, same articles), so the improvement may be overstated.
- These results measure retrieval only. They do not show that the final answers became more accurate. Answer quality was checked manually on a few clauses and was not measured systematically.

## Run it yourself

```bash
git clone https://github.com/Nur-hidir/legal-contract-app
cd legal-contract-app
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file:

```
GROQ_API_KEY=your_key_here
```

On Streamlit Cloud, add the key under Settings > Secrets as `GROQ_API_KEY = "your_key_here"`.

Start the app and upload the law files from the sidebar:

```bash
streamlit run app.py
```

**Run the rule tests**

```bash
python test_rules.py
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
rules.py          Rule-based clause checks (no AI)
ingest.py         Article-level chunking and clause splitting
finetune.py       Training data preparation, training, evaluation
eval_set.json     Evaluation clauses
test_ingest.py    Offline test for chunking
test_rules.py     Tests for the rule-based checks
data/laws/        Law files
data/sample/      Example contract (fictional)
```

## Data and privacy

- Law texts are from the official legislation site mevzuat.gov.tr:
  - Turkish Code of Obligations (No. 6098): https://www.mevzuat.gov.tr/MevzuatMetin/1.5.6098.pdf
  - Labor Law (No. 4857): https://www.mevzuat.gov.tr/MevzuatMetin/1.5.4857.pdf
- Example contracts in this repository are fictional. Do not upload real contracts with personal data: clause text is sent to the Groq API for answer generation.
- `.env`, model weights and index caches are not committed.

## Known limitations

- Covers only the uploaded laws; no case law or regulations.
- Answers come from an LLM and can be wrong. Always check the cited article.
- A test on a sample full contract showed both false alarms (a clause that repeats the law was marked as violating) and misses (a non-compete clause got "no relevant provision"). Results can also vary between runs.
- Rule-based checks are keyword-based and cover only four topics.
- The live demo may use the base embedding model, because the fine-tuned model is not hosted with the app. The retrieval metrics above were measured locally with the fine-tuned model.
- Free API quotas can make the live demo slow or temporarily unavailable.
