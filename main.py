import os
import uuid
import shutil
import sqlite3
from dotenv import load_dotenv
from auth import create_access_token, verify_user
from openai import OpenAI
#import chromadb
#from sentence_transformers import SentenceTransformer
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
import time
from fastapi import Request
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
from fastapi import Depends
from auth import get_current_user_id
import fitz 
import pandas as pd 
from docx import Document 
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from starlette.requests import Request
from docx import Document
import markdown
from fastapi import Depends
from fastapi import Query
from fastapi.responses import StreamingResponse
import mimetypes
from auth import get_user_id_from_token
#import pytesseract, io 
#from pdf2image import convert_from_path
from PIL import Image
from docx import Document
import pandas as pd
#from docx2pdf import convert
import tempfile
import markdown
import mammoth

 

    
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
selected_files = {}
client = OpenAI(api_key=api_key, base_url=base_url)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
app = FastAPI()
#app.middleware("http")(jwt_auth_middleware)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def read_index():
    return FileResponse("frontend/index.html")
async def jwt_auth_middleware(request: Request, call_next):

    if request.url.path.startswith("/static") or request.url.path == "/" or request.url.path.endswith(".html"):
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Token missing or invalid"})

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=["HS256"])
        request.state.user = payload
    except JWTError:
        return JSONResponse(status_code=401, content={"detail": "Invalid token"})

    return await call_next(request)


   
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="RAG Chatbot",
        version="1.0",
        description=" RAGAPI",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method.setdefault("security", []).append({"BearerAuth": []})
    app.openapi_schema = openapi_schema
    return app.openapi_schema
app.openapi = custom_openapi




 
conn = sqlite3.connect("ragbot_logs.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS qa_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    file_path TEXT,
    question TEXT,
    context TEXT,
    answer TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)
""")
conn.commit()


def extract_text(file_path):
    ext = os.path.splitext(file_path)[-1].lower()

    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    elif ext == ".pdf":
        doc = fitz.open(file_path)
        text =  "\n\n".join([page.get_text() for page in doc])
        
        if not text.strip():
            text= ""
            images = convert_from_path(file_path, dpi=300)
            for img in images:
                text += pytesseract.image_to_string(img) + "/n"
        return text

    elif ext == ".docx":
        doc = fitz.open(file_path)
        text =  "\n\n".join([page.get_text() for page in doc])
        
        if not text.strip():
            text= ""
            images = convert_from_path(file_path, dpi=300)
            for img in images:
                text += pytesseract.image_to_string(img) + "/n"
        return text
       
    elif ext == ".csv":
        df = pd.read_csv(file_path)
        return df.to_string(index=False)

    elif ext == ".xlsx":
        df = pd.read_excel(file_path)
        return df.to_string(index=False)

    else:
        raise ValueError("Unsupported file type")
    
    
    

@app.post("/register")
def register(username: str = Form(...), password: str = Form(...)):
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return {"message": "User registered successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already exists.")

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    user_id = verify_user(username, password)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(data={"sub": username, "id": user_id})
    return {"access_token": token, "token_type": "bearer", "user_id": user_id }


@app.get("/start")
def list_user_files(user_id: int = Depends(get_current_user_id)):
    cursor.execute("SELECT id, file_path FROM qa_log WHERE user_id = ?", (user_id,))
    files = [{"id": row[0], "file_path": row[1]} for row in cursor.fetchall()]
    return files

@app.post("/start")
def start_session(user_id: int = Depends(get_current_user_id)):
    try:
        print("Start_session called for user_id:", user_id)
        cursor.execute("SELECT DISTINCT file_path FROM qa_log WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        print("Files fetched from DB:", rows)
        files = [row[0] for row in rows]
        return {"id": user_id, "files": files, "message": "Fetched uploaded files."}
    except Exception as e:
        print(" Error in /start:", e)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/upload")
def upload_file(user_id: int = Depends(get_current_user_id), file: UploadFile = File(...)):
    ext =os.path.splitext(file.filename)[-1].lower()
    allowed_formats = [".txt", ".pdf", ".docx", ".csv", ".xlsx"]
    if ext not in allowed_formats:
        raise HTTPException(status_code=400, detail="Unsupported file format. Allowed formats: txt, pdf, docx, csv, xlsx.")
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{user_id}_{uuid.uuid4().hex}{ext}"
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
             
    cursor.execute("INSERT INTO qa_log (user_id, file_path) VALUES (?, ?)", (user_id, file_path))
    conn.commit()
    return {"message": "File uploaded.", "file_path": file_path}

@app.post("/select")
def select_file(file_path: str = Form(...), user_id: int = Depends(get_current_user_id)):
    cursor.execute("""
                   INSERT INTO user_selection (user_id, file_path)
                   VALUES(?,?)
                   ON CONFLICT(user_id) DO UPDATE SET file_path = excluded.file_path""", (user_id, file_path))
    conn.commit()

    return {"message": "File selected."}

@app.get("/history")
async def get_chat_history(
    user_id: int = Depends(get_current_user_id), file_path: str = Query(...)):
    conn = sqlite3.connect("ragbot_logs.db")
    cursor = conn.cursor()
    cursor.execute("""
                   SELECT question, answer FROM qa_log
                   WHERE user_id = ? AND file_path = ?
                   ORDER BY timestamp ASC""", (user_id, file_path))
    rows = cursor.fetchall()
    conn.close()
    return {
        "chat": [{"question": q, "answer":markdown.markdown(a) if a else""} for q, a in rows]
    }

@app.post("/ask")
def ask_question(
    question: str = Form(...),
    user_id: int = Depends(get_current_user_id)
):
    #  1. Get selected file for user
    cursor.execute("SELECT file_path FROM user_selection WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="No file selected.")
    file_path = row[0]

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="No file found.")

    #  2. Load chat history for this file
    cursor.execute("""
        SELECT question, answer FROM qa_log
        WHERE user_id = ? AND file_path = ?
        ORDER BY timestamp ASC
    """, (user_id, file_path))
    chat_history = cursor.fetchall()

    #  3. Extract + chunk file
    text = extract_text(file_path)
    documents = [line.strip() for line in text.splitlines() if line.strip()]
    chunk_size = 5
    chunks = ["\n".join(documents[i:i+chunk_size]) for i in range(0, len(documents), chunk_size)]
    embeddings = embedding_model.encode(chunks)

    #  4. ChromaDB collection
    db = chromadb.Client()
    collection = db.get_or_create_collection(name=f"user_{user_id}_collection")

    # Add chunks to collection (with unique IDs)
    for i, chunk in enumerate(chunks):
        #doc_id = f"{user_id}_{file_path}_{i}"
        collection.add(
            documents=[chunk],
            embeddings=[embeddings[i].tolist()],
            ids=[str(i)],
            metadatas=[{"user_id": str(user_id), "file_path": file_path}]
        )

    #  5. Query with filters 
    query_embedding = embedding_model.encode([question])
    results = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=3)

    context = "\n\n".join(results["documents"][0]) 

    #  6. Build conversation
    messages = [
        {"role": "system", "content": f"""
# RAGBOT AI Assistant Capabilities

## Overview
I am RAGBOT 🤖, a Retrieval-Augmented Generation (RAG) based AI assistant.
My main role is to help users interact with their uploaded documents by answering questions,
summarizing content, and extracting insights using the provided context.

## General Capabilities

### Information Processing
- Answer questions based only on the given context:
{context}
- Summarize long sections into clear points
- Highlight important facts, figures, or arguments
- Compare multiple documents when needed

### Content Creation
- Provide structured, well-formatted answers
- Use markdown (bullet points, headings, tables) when useful
- Draft concise explanations instead of long paragraphs

### Problem Solving
- If information is missing from context, reply politely:
  "I couldn’t find that information in the uploaded documents."
- Never hallucinate or invent details not present in context
- Suggest related queries the user might try

## Style & Communication
- Friendly, professional, and clear tone
- Answers should be concise but informative
- Avoid unnecessary jargon unless user asks for detail

## Limitations
- Do not answer outside the provided context
- Respect privacy: never request sensitive personal data
- No speculation or assumptions

## Task Approach
1. Read the context carefully
2. Identify key information relevant to the question
3. Respond with a structured and clear answer
4. If answer not found, politely decline with explanation
"""
}
    ]
    for q, a in chat_history:
        messages.append({"role": "user", "content": q})
        messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": question})

    #  7. Get answer from LLM
    response = client.chat.completions.create(
        model="mistralai/mistral-7b-instruct:free",
        messages=messages
    )
    answer = response.choices[0].message.content

    #  8. Save to DB
    cursor.execute("""
        INSERT INTO qa_log (user_id, file_path, question, context, answer)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, file_path, question, context, answer))
    conn.commit()

    #  9. Return result
    html_output = markdown.markdown(answer)
    return {
        "question": question,
        "answer": answer,
        "html": html_output
    }


@app.get("/viewfiles")
def view_files(user_id: int = Depends(get_current_user_id)):
    conn = sqlite3.connect("ragbot_logs.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT file_path FROM user_selection WHERE user_id=? ORDER BY rowid DESC LIMIT 1", (user_id,))
    result = cursor.fetchone()
    conn.close()
 
     
    if not result:
        raise HTTPException(status_code=404, detail="No file found")

    file_path = result[0]
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".docx":
        with open(file_path, "rb") as docx_file:
            result = mammoth.convert_to_html(docx_file)
            html = result.value
        return HTMLResponse(content=f"<div style='padding:20px;'>{html}</div>")
                                                                      
         
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return HTMLResponse(content=f"<pre>{text}</pre>")
    
    elif ext in [".csv",".xlsx"]:
        import pandas as pd
        df = pd.read_csv(file_path) if ext == ".csv" else pd.read_excel(file_path)
        return HTMLResponse(content=df.to_html(classes="table table-bordered"))
    
    elif ext == ".pdf":
        return StreamingResponse(
            open(file_path, "rb"),
            media_type= "application/pdf",
            headers={"Content-Disposition": "inline; filename=file.pdf"}
            
        )
        
        
    
   
    content_type, _ = mimetypes.guess_type(file_path)
    return StreamingResponse(
        open(file_path, "rb"),
        media_type=content_type or "application/octet-stream",
        headers={"Content-Disposition": f"inline; filename={os.path.basename(file_path)}"}
    )
    
    
    

   
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

   
   
   
   
   
   
   
   
   
