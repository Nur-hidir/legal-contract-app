import io
import os
import re
import hashlib
import tempfile
import streamlit as st
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

# İçe Aktarma: Groq modelini kullanmak için değiştirildi
from langchain_groq import ChatGroq

try:
    from docx import Document as WordBelgesi
    DOCX_DESTEGI = True
except ImportError:
    DOCX_DESTEGI = False

from ingest import madde_bazli_parcala, sozlesme_maddelerine_ayir

load_dotenv()

# Groq Modelini Başlat (Llama 3.3 70B modeli çok hızlı ve Türkçede çok başarılıdır)
groq_api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
model = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.3,
    api_key=groq_api_key
)

TEMEL_MODEL = "intfloat/multilingual-e5-small"
EGITILEN_MODEL = os.path.join("models", "e5-hukuk")
MODEL_ADI = EGITILEN_MODEL if os.path.isdir(EGITILEN_MODEL) else TEMEL_MODEL

ESIK = float(os.getenv("ESIK", "0.60"))
GELISTIRICI = os.getenv("GELISTIRICI") == "1"

DESTEKLENEN_UZANTILAR = ["pdf", "txt"] + (["docx"] if DOCX_DESTEGI else [])

st.set_page_config(
    page_title="Sözleşme Analizi",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ---------- TASARIM ----------
STIL = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@400;700&family=Inter:wght@400;500;600&display=swap');

:root {
    --lacivert: #0E1B36;
    --lacivert-orta: #152647;
    --lacivert-acik: #1D3360;
    --cizgi: #2F4A7D;
    --altin: #C9A75F;
    --beyaz: #FFFFFF;
    --siyah: #222222;
    --gri-koyu: #444444;
    --gri-acik: #E0E0E0;
    --krem: #F3EFE6;
}

html, body, .stApp, [data-testid="stSidebar"], p, label, input, textarea, button {
    font-family: 'Inter', sans-serif;
}

.stApp { background: var(--beyaz) !important; color: var(--siyah) !important; }

.hero-container {
    background-color: var(--lacivert) !important;
    margin: 0 0 2rem 0;
    padding: 2.5rem 2rem;
    border-radius: 16px;
    box-shadow: 0 8px 24px rgba(14, 27, 54, 0.15);
}

.hero { text-align: center; }
.hero .ikon { font-size: 2.5rem; margin-bottom: 0.5rem; }

.hero h1, .hero h1 *, .hero-container h1, .hero-container h1 span { 
    font-family: 'Libre Baskerville', Georgia, serif !important;
    font-size: 1.85rem !important; 
    margin: 0 !important; 
    line-height: 1.35 !important; 
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
.hero p, .hero p * { 
    color: var(--krem) !important; 
    -webkit-text-fill-color: var(--krem) !important;
    margin: 0.6rem 0 0 0 !important; 
    font-size: 1rem !important; 
}
.hero .cizgi { width: 60px; height: 3px; background: var(--altin); margin: 1.2rem auto 0; border-radius: 2px; }

#MainMenu, footer, .stDeployButton, [data-testid="stAppDeployButton"] {
    display: none !important;
}

header[data-testid="stHeader"] { background: transparent !important; }

[data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"] {
    background-color: var(--lacivert) !important;
    border: 2px solid var(--altin) !important;
    border-radius: 8px !important;
    padding: 4px !important;
    margin: 8px !important;
    z-index: 999999 !important;
}
[data-testid="collapsedControl"] svg, [data-testid="stSidebarCollapsedControl"] svg {
    color: var(--altin) !important; 
    fill: var(--altin) !important;
    width: 24px !important;
    height: 24px !important;
}

.block-container { max-width: 820px; padding-top: 2rem; padding-bottom: 8rem; }

[data-testid="stSidebar"] { 
    background: var(--lacivert) !important; 
    border-right: 2px solid var(--altin) !important; 
}
[data-testid="stSidebar"] *, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span { 
    color: var(--krem) !important; 
}
[data-testid="stSidebar"] h2 { 
    font-family: 'Libre Baskerville', Georgia, serif !important; 
    color: var(--beyaz) !important;
}
[data-testid="stFileUploaderDropzone"] {
    border: 1.5px dashed var(--altin); background: var(--lacivert-orta); border-radius: 12px;
}
[data-testid="stFileUploaderDropzone"] button {
    background: var(--altin) !important; border: 0 !important; border-radius: 8px;
}
[data-testid="stFileUploaderDropzone"] button, [data-testid="stFileUploaderDropzone"] button * {
    color: var(--lacivert) !important; font-weight: 600 !important;
}
[data-testid="stFileUploaderFile"] { background: var(--lacivert-orta); border-radius: 8px; }
[data-testid="stFileUploaderFile"] * { color: var(--krem) !important; }

div[role="radiogroup"] label, div[role="radiogroup"] p, div[role="radiogroup"] span { 
    color: var(--siyah) !important; 
    font-weight: 500;
}

div[data-testid="stChatMessage"] {
    background: #F8F9FA;
    border: 1px solid var(--gri-acik);
    border-radius: 14px;
    padding: 1rem 1.1rem;
    margin-bottom: 0.9rem;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background: #E9ECEF; }
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) { border-left: 4px solid var(--altin); }
[data-testid="stChatMessageAvatarUser"] { background: var(--lacivert-acik) !important; }
[data-testid="stChatMessageAvatarAssistant"] { background: var(--altin) !important; }
div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li, div[data-testid="stChatMessage"] span { 
    color: var(--siyah) !important; 
}

div[data-testid="stBottom"], div[data-testid="stBottom"] > div { background: var(--beyaz) !important; }
div[data-testid="stChatInput"] {
    border: 1.5px solid var(--altin);
    border-radius: 16px;
    background: var(--lacivert) !important;
    box-shadow: 0 6px 22px rgba(0, 0, 0, 0.25);
    margin-bottom: 1rem;
}
div[data-testid="stChatInput"]:focus-within { border-color: var(--krem); }
div[data-testid="stChatInput"] > div,
div[data-testid="stChatInput"] [data-baseweb="textarea"],
div[data-testid="stChatInput"] [data-baseweb="base-input"],
div[data-testid="stChatInput"] textarea {
    background: var(--lacivert) !important;
    color: var(--beyaz) !important;
    -webkit-text-fill-color: var(--beyaz) !important;
}
div[data-testid="stChatInput"] textarea::placeholder { color: var(--gri-acik) !important; -webkit-text-fill-color: var(--gri-acik) !important; }
button[data-testid="stChatInputSubmitButton"] { background: var(--altin) !important; border-radius: 10px; }
button[data-testid="stChatInputSubmitButton"] svg { color: var(--lacivert) !important; fill: var(--lacivert) !important; }

.stButton > button[kind="primary"] {
    background: var(--altin) !important; border: 0; border-radius: 10px;
    padding: 0.55rem 1.3rem; font-weight: 600;
}
.stButton > button[kind="primary"], .stButton > button[kind="primary"] * { color: var(--lacivert) !important; }
.stButton > button[kind="primary"]:hover { background: var(--lacivert) !important; color: var(--altin) !important;}

div[data-testid="stAlert"] {
    background: #F0F4F8 !important;
    border: 1px solid var(--gri-acik); border-radius: 12px;
}
div[data-testid="stAlert"], div[data-testid="stAlert"] * { color: var(--siyah) !important; }

div[data-testid="stExpander"] { border: 1px solid var(--gri-acik); border-radius: 12px; background: #FFFFFF; }
div[data-testid="stExpander"] details, div[data-testid="stExpander"] summary { background: #FFFFFF; border-radius: 12px; }
div[data-testid="stExpander"] summary * { color: var(--siyah) !important; }

.ozet { display: flex; gap: 0.6rem; flex-wrap: wrap; margin: 1rem 0 1.2rem; }
.rozet { padding: 0.35rem 0.9rem; border-radius: 999px; font-size: 0.9rem; font-weight: 600; border: 1px solid; }
.rozet.kirmizi { color: #D32F2F !important; background: rgba(211, 47, 47, 0.1); border-color: rgba(211, 47, 47, 0.3); }
.rozet.yesil { color: #2E7D32 !important; background: rgba(46, 125, 50, 0.1); border-color: rgba(46, 125, 50, 0.3); }
.rozet.gri { color: var(--gri-koyu) !important; background: rgba(169, 179, 199, 0.2); border-color: rgba(169, 179, 199, 0.5); }
</style>
"""
st.markdown(STIL, unsafe_allow_html=True)

st.markdown(
    """
    <div class="hero-container">
        <div class="hero">
            <div class="ikon">⚖️</div>
            <h1 style="color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important;">Sözleşme maddenizi kanunla karşılaştırın</h1>
            <p style="color: #F3EFE6 !important; -webkit-text-fill-color: #F3EFE6 !important;">Yüklediğiniz kanunlara göre kısa ve sade analiz.</p>
            <div class="cizgi"></div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []


# ---------- DOSYA OKUMA (PDF, Word, TXT) ----------
def metin_coz(veri):
    for kodlama in ("utf-8-sig", "cp1254"):
        try:
            return veri.decode(kodlama)
        except UnicodeDecodeError:
            continue
    return veri.decode("latin-1", errors="ignore")


def docx_metni(veri):
    belg = WordBelgesi(io.BytesIO(veri))
    satirlar = [p.text for p in belg.paragraphs if p.text.strip()]
    for tablo in belg.tables:
        for satir in tablo.rows:
            hucreler = [h.text.strip() for h in satir.cells if h.text.strip()]
            if hucreler:
                satirlar.append(" | ".join(hucreler))
    return "\n".join(satirlar)


def dosyadan_sayfalar(dosya):
    ad = dosya.name.lower()
    if ad.endswith(".pdf"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(dosya.getvalue())
            tmp_path = tmp.name
        try:
            return PyPDFLoader(tmp_path).load()
        finally:
            os.unlink(tmp_path)
    if ad.endswith(".docx"):
        metin = docx_metni(dosya.getvalue())
    else:
        metin = metin_coz(dosya.getvalue())
    return [Document(page_content=metin, metadata={"page": 0})]


def sozlesme_dosyasini_oku(dosya):
    return "\n".join(s.page_content for s in dosyadan_sayfalar(dosya))


# ---------- ARAMA ALTYAPISI ----------
class YerelEmbeddings(Embeddings):
    def __init__(self, model_adi):
        self.model = SentenceTransformer(model_adi)

    def embed_documents(self, texts):
        return self.model.encode(
            ["passage: " + t for t in texts],
            batch_size=16, normalize_embeddings=True,
        ).tolist()

    def embed_query(self, text):
        return self.model.encode("query: " + text, normalize_embeddings=True).tolist()


@st.cache_resource(show_spinner=False)
def embedding_modeli(model_adi):
    return YerelEmbeddings(model_adi)


@st.cache_resource(show_spinner=False)
def veritabanini_olustur(_yuklenen_dosyalar, cache_anahtari, model_adi):
    embeddings = embedding_modeli(model_adi)

    anahtar = hashlib.md5(f"{cache_anahtari}|{model_adi}".encode()).hexdigest()
    klasor = os.path.join("data", "faiss_cache_yerel", anahtar)
    if os.path.exists(klasor):
        return FAISS.load_local(klasor, embeddings, allow_dangerous_deserialization=True)

    tum_parcalar = []
    for dosya in _yuklenen_dosyalar:
        sayfalar = dosyadan_sayfalar(dosya)
        tum_parcalar.extend(madde_bazli_parcala(sayfalar, dosya.name))

    db = FAISS.from_documents(tum_parcalar, embeddings)
    os.makedirs(klasor, exist_ok=True)
    db.save_local(klasor)
    return db


def ilgili_hukum_yok_mu(cevap):
    temiz = cevap.upper().replace("İ", "I").replace("Ü", "U").replace(" ", "_")
    return "ILGILI_HUKUM_YOK" in temiz


def analiz_et(madde_metni, vektor_db, esik):
    sonuclar = vektor_db.similarity_search_with_score(madde_metni, k=3)
    en_iyi_skor = float(min(skor for _, skor in sonuclar))

    if en_iyi_skor > esik:
        return False, "Bu madde için yüklenen kanunlarda ilgili bir hüküm bulunamadı.", [], en_iyi_skor

    belgeler = [doc for doc, _ in sonuclar]
    context = ""
    for doc in belgeler:
        context += (
            f"\nKaynak: {doc.metadata.get('source', 'Bilinmeyen')} | "
            f"{doc.metadata.get('madde_no', '?')} | Sayfa {doc.metadata.get('sayfa', '?')}\n"
            f"{doc.page_content}\n"
        )

    prompt = f"""
    Sen profesyonel ve tarafsız bir sözleşme analiz asistanısın. Yasal tavsiye verme.
    Aşağıdaki sözleşme maddesini ve ilgili kanunları incele.

    ÖNCELİKLİ KURAL: Önce, verilen kanun maddelerinden en az biri sözleşme maddesinin konusunu doğrudan düzenliyor mu karar ver. Yalnızca "sözleşme" kelimesinin geçmesi ya da genel hükümler olması yeterli DEĞİLDİR. Doğrudan düzenlemiyorsa cevabının TAMAMI sadece şu tek kelime olsun: ILGILI_HUKUM_YOK. Doğrudan düzenliyorsa aşağıdaki kuralları uygula.

    KURAL 1: Kesinlikle ağır hukuk jargonu, eski kelimeler (örn: fesih, akit, muvazaa, cezai şart) veya karmaşık uzun cümleler KULLANMA.
    KURAL 2: Samimi, laubali, espirili veya "arkadaşça" bir dil KULLANMA. Doğrudan, profesyonel, ciddi ve net ol.
    KURAL 3: Sadece şu iki başlık altında çok kısa ve öz bir özet çıkar:

    **1. Çalışan İçin Somut Risk:** (Bu madde çalışanın maaşını, mesaisini, istifasını veya geleceğini somut olarak nasıl etkiler?)
    **2. Kanuna Aykırı Mı?:** (Evet veya Hayır de. Neden aykırı olduğunu tek cümleyle basitçe açıkla ve kanun adı ile madde numarasını belirt.)

    Sözleşme Maddesi: {madde_metni}
    İlgili Kanunlar: {context}
    """

    # GROQ API ÇAĞRISI
    try:
        yanit = model.invoke(prompt)
        cevap = yanit.content
    except Exception as hata:
        print("GROQ HATASI:", repr(hata), flush=True)
        return False, f"Şu anda analiz yapılamadı ({type(hata).__name__}). Lütfen tekrar deneyin.", [], en_iyi_skor

    if ilgili_hukum_yok_mu(cevap):
        return False, "Bu madde için yüklenen kanunlarda ilgili bir hüküm bulunamadı.", [], en_iyi_skor
    return True, cevap, belgeler, en_iyi_skor


def aykiri_mi(cevap):
    m = re.search(r"Kanuna Aykırı Mı\?[\s:*]*\b(Evet|Hayır)", cevap, re.IGNORECASE)
    return bool(m) and m.group(1).lower() == "evet"


def kaynaklari_goster(belgeler, mesafe):
    with st.expander("📚 Kullanılan kanun maddeleri"):
        if GELISTIRICI:
            st.caption(f"En iyi eşleşme mesafesi: {mesafe:.3f} (düşük = daha benzer)")
        for doc in belgeler:
            st.markdown(
                f"**{doc.metadata.get('source', '?')}** — "
                f"{doc.metadata.get('madde_no', '?')} (Sayfa {doc.metadata.get('sayfa', '?')})"
            )
            st.caption(doc.page_content[:500])


def mesaji_goster(msg):
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and not msg.get("ilgili", True):
            st.info(msg["content"])
        else:
            st.markdown(msg["content"])
        if msg.get("belgeler"):
            kaynaklari_goster(msg["belgeler"], msg["mesafe"])


# ---------- KENAR ÇUBUĞU ----------
with st.sidebar:
    st.header("Mevzuat")
    yuklenen_kanunlar = st.file_uploader(
        "Kanun dosyalarını yükleyin",
        type=DESTEKLENEN_UZANTILAR,
        accept_multiple_files=True,
        help="PDF" + (", Word (.docx)" if DOCX_DESTEGI else "") + " ve metin (.txt) dosyaları desteklenir.",
    )

    vektor_db = None
    if yuklenen_kanunlar:
        cache_anahtari = "-".join([f"{f.name}_{f.size}" for f in yuklenen_kanunlar])
        with st.spinner("Dosyalar işleniyor, ilk yüklemede 1-2 dakika sürebilir..."):
            vektor_db = veritabanini_olustur(yuklenen_kanunlar, cache_anahtari, MODEL_ADI)
        st.success("✅ Analize hazır")

    st.caption("Bu sistem yasal tavsiye vermez, ön bilgilendirme amaçlıdır.")


# ---------- MOD SEÇİMİ ----------
mod = st.radio(
    "Mod", ["Tek Madde", "Tüm Sözleşme"],
    horizontal=True, label_visibility="collapsed",
)

# ---------- TEK MADDE ----------
if mod == "Tek Madde":
    for msg in st.session_state.messages:
        mesaji_goster(msg)

    user_input = st.chat_input("Sözleşme maddesini buraya yapıştırın...")

    if user_input:
        kullanici_mesaji = {"role": "user", "content": user_input}
        st.session_state.messages.append(kullanici_mesaji)
        mesaji_goster(kullanici_mesaji)

        with st.chat_message("assistant"):
            if not vektor_db:
                st.error("Lütfen önce soldaki panelden kanun dosyası yükleyin.")
            else:
                with st.spinner("İnceleniyor..."):
                    ilgili, cevap, belgeler, mesafe = analiz_et(user_input, vektor_db, ESIK)
                if ilgili:
                    st.markdown(cevap)
                    kaynaklari_goster(belgeler, mesafe)
                else:
                    st.info(cevap)
                    if GELISTIRICI:
                        st.caption(f"En iyi mesafe: {mesafe:.3f}, eşik: {ESIK:.2f}")
                st.session_state.messages.append({
                    "role": "assistant", "content": cevap, "ilgili": ilgili,
                    "belgeler": belgeler, "mesafe": mesafe,
                })

# ---------- TÜM SÖZLEŞME ----------
else:
    sozlesme_dosyasi = st.file_uploader(
        "Sözleşmeyi yükleyin", type=DESTEKLENEN_UZANTILAR, key="sozlesme",
        help="PDF" + (", Word (.docx)" if DOCX_DESTEGI else "") + " veya metin (.txt) dosyası.",
    )

    if st.button("Tüm Sözleşmeyi Analiz Et", type="primary"):
        if not vektor_db:
            st.error("Lütfen önce soldaki panelden kanun dosyası yükleyin.")
        elif not sozlesme_dosyasi:
            st.error("Lütfen bir sözleşme dosyası yükleyin.")
        else:
            maddeler = sozlesme_maddelerine_ayir(sozlesme_dosyasini_oku(sozlesme_dosyasi))
            st.write(f"**{len(maddeler)} madde bulundu.**")

            ilerleme = st.progress(0)
            sonuclar = []
            for i, madde in enumerate(maddeler):
                ilgili, cevap, belgeler, mesafe = analiz_et(madde, vektor_db, ESIK)
                sonuclar.append({
                    "madde": madde,
                    "ilgili": ilgili,
                    "cevap": cevap,
                    "belgeler": belgeler,
                    "mesafe": mesafe,
                    "riskli": ilgili and aykiri_mi(cevap),
                })
                ilerleme.progress((i + 1) / len(maddeler))

            riskli = sum(1 for s in sonuclar if s["riskli"])
            uygun = sum(1 for s in sonuclar if s["ilgili"] and not s["riskli"])
            ilgisiz = sum(1 for s in sonuclar if not s["ilgili"])
            st.markdown(
                f'<div class="ozet">'
                f'<span class="rozet kirmizi">🔴 {riskli} aykırı</span>'
                f'<span class="rozet yesil">🟢 {uygun} uygun</span>'
                f'<span class="rozet gri">⚪ {ilgisiz} ilgili hüküm yok</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            for s in sorted(sonuclar, key=lambda x: not x["riskli"]):
                if s["riskli"]:
                    simge = "🔴"
                elif s["ilgili"]:
                    simge = "🟢"
                else:
                    simge = "⚪"
                with st.expander(f"{simge} {s['madde'][:90]}..."):
                    st.caption(s["madde"])
                    if s["ilgili"]:
                        st.markdown(s["cevap"])
                        kaynaklari_goster(s["belgeler"], s["mesafe"])
                    else:
                        st.info(s["cevap"])
