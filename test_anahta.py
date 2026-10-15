import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()
e = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)
print("Başarılı, vektör boyutu:", len(e.embed_query("merhaba")))