"""FastAPI entrypoint: uvicorn rag_api:app --host 127.0.0.1 --port 8766."""
import os,secrets,time,threading
from pathlib import Path
from collections import deque
from fastapi import FastAPI,Header,HTTPException,Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,Field,ConfigDict
from typing import Literal
from rag.pipeline import Pipeline
ROOT=Path(__file__).parent
PUBLIC=os.getenv('RAG_PUBLIC','false').lower()=='true'
ACCESS=os.getenv('RAG_ACCESS_TOKEN','')
if PUBLIC and len(ACCESS)<24:raise RuntimeError('Public mode requires RAG_ACCESS_TOKEN of at least 24 characters')
SESSION=secrets.token_urlsafe(32)
LOCK=threading.Lock();CALLS=deque()
app=FastAPI(title='Project Brief - Evidence Desk',version='2.0',docs_url=None if PUBLIC else '/docs',redoc_url=None)
class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class Document(Strict):
    name:str=Field(min_length=1,max_length=200)
    text:str=Field(min_length=1,max_length=250000)
class Ingest(Strict):
    documents:list[Document]=Field(min_length=1,max_length=30)
    size:int=Field(default=180,ge=30,le=800)
    overlap:int=Field(default=35,ge=0,le=200)
    embedding:Literal['offline','openai','ollama']='offline'
    model:str=Field(default='hash-v1',min_length=1,max_length=100)
    vector_store:Literal['sqlite','chroma']='sqlite'
class Ask(Strict):
    index_id:str=Field(min_length=32,max_length=32,pattern='^[0-9a-f]+$')
    question:str=Field(min_length=1,max_length=2000)
    config:Literal['dense','hybrid','rerank']='hybrid'
    reranker:Literal['offline','cohere']='offline'
    generator:Literal['offline','openai','ollama']='offline'

def authorize(token):
    expected=ACCESS if PUBLIC or ACCESS else SESSION
    if not token or not secrets.compare_digest(token,'Bearer '+expected):raise HTTPException(401,'Authentication required')
    with LOCK:
        now=time.monotonic()
        while CALLS and CALLS[0]<now-60:CALLS.popleft()
        if len(CALLS)>=int(os.getenv('RAG_REQUESTS_PER_MINUTE','12')):raise HTTPException(429,'Rate limit reached; wait one minute')
        CALLS.append(now)

def pipeline():return Pipeline(os.getenv('RAG_DB','local_data/rag.sqlite'))
@app.middleware('http')
async def body_limit(request:Request,call_next):
    # Enforce actual body bytes, not just user-supplied Content-Length.
    if request.method=='POST':
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>1500000:
                from fastapi.responses import JSONResponse
                return JSONResponse({'detail':'Request body too large'},status_code=413)
        request._body=bytes(body)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff';response.headers['Cache-Control']='no-store'
    return response
@app.get('/',response_class=HTMLResponse)
def home():return (ROOT/'rag.html').read_text().replace('__SESSION__','' if PUBLIC or ACCESS else SESSION)
@app.get('/health')
def health():return {'status':'ok','version':'2.0'}
@app.get('/api/sample')
def sample(authorization:str|None=Header(default=None)):
    authorize(authorization)
    return {'documents':[{'name':p.name,'text':p.read_text()} for p in sorted((ROOT/'corpus').glob('*.md'))]}
@app.post('/api/ingest')
def ingest(body:Ingest,authorization:str|None=Header(default=None)):
    authorize(authorization)
    try:return pipeline().ingest(**body.model_dump())
    except (ValueError,ImportError) as e:raise HTTPException(400,str(e))
@app.post('/api/ask')
def ask(body:Ask,authorization:str|None=Header(default=None)):
    authorize(authorization)
    try:return pipeline().ask(**body.model_dump())
    except (ValueError,ImportError) as e:raise HTTPException(400,str(e))
