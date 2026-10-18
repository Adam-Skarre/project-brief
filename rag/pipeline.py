import hashlib,json,time,uuid,os
from pathlib import Path
from .retrieval import chunk_document,BM25,cosine,rrf
from .providers import Providers,observe
from .storage import Store

VERSION='rag-1.0'
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def validate_answer(answer,chunks):
    if not isinstance(answer,dict) or set(answer)!={'abstain','reason','claims'}:raise ValueError('Invalid answer schema')
    if type(answer['abstain']) is not bool or not isinstance(answer['reason'],str) or len(answer['reason'])>2000:raise ValueError('Invalid abstention fields')
    if not isinstance(answer['claims'],list) or len(answer['claims'])>20:raise ValueError('Invalid claims')
    if answer['abstain']:
        if answer['claims'] or not answer['reason'].strip():raise ValueError('Abstention must explain and contain no claims')
    elif not answer['claims']:raise ValueError('Answer must contain cited claims or abstain')
    known={c['chunk_id']:c['text'] for c in chunks}
    for claim in answer['claims']:
        if not isinstance(claim,dict) or set(claim)!={'text','evidence'}:raise ValueError('Invalid claim')
        if not isinstance(claim['text'],str) or not claim['text'].strip() or len(claim['text'])>3000:raise ValueError('Invalid claim text')
        if not isinstance(claim['evidence'],list) or not 1<=len(claim['evidence'])<=5:raise ValueError('Every claim needs evidence')
        for e in claim['evidence']:
            if not isinstance(e,dict) or set(e)!={'chunk_id','quote'}:raise ValueError('Invalid evidence schema')
            if not isinstance(e['chunk_id'],str) or e['chunk_id'] not in known:raise ValueError('Unknown cited chunk')
            if not isinstance(e['quote'],str) or not e['quote'].strip() or e['quote'] not in known[e['chunk_id']]:raise ValueError('Evidence quote is not verbatim in the cited chunk')
    return answer

class Pipeline:
    def __init__(self,path='local_data/rag.sqlite'):
        self.store=Store(path);self.provider=Providers(self.store)
    def ingest(self,documents,size=180,overlap=35,embedding='offline',model='hash-v1',vector_store='sqlite'):
        if not isinstance(documents,list) or not 1<=len(documents)<=30:raise ValueError('Supply 1-30 documents')
        if vector_store not in ('sqlite','chroma'):raise ValueError('Unknown vector store')
        names=[d['name'] for d in documents]
        if len(names)!=len(set(names)):raise ValueError('Document names must be unique within an index')
        if sum(len(d['text']) for d in documents)>1000000:raise ValueError('Corpus exceeds 1 million characters')
        config={'size':size,'overlap':overlap,'embedding':embedding,'model':model,'vector_store':vector_store,'version':VERSION}
        index_id=digest([documents,config])[:32]
        try:
            previous=self.store.get_index(index_id)
            return {'index_id':index_id,'chunks':len(previous['chunks']),'config':config,'cached':True}
        except ValueError:pass
        chunks=[c for d in documents for c in chunk_document(d['name'],d['text'],size,overlap)]
        if len(chunks)>1000:raise ValueError('Maximum 1000 chunks; use larger chunks or smaller corpus')
        self.provider.events=[];start=time.perf_counter()
        with observe('ingestion',input={'names':names,'config':config}):
            vectors=self.provider.embed([c['text'] for c in chunks],embedding,model)
            if vector_store=='chroma':
                collection=self.chroma(index_id)
                collection.upsert(ids=[c['chunk_id'] for c in chunks],embeddings=vectors,documents=[c['text'] for c in chunks])
            payload={'chunks':chunks,'vectors':vectors,'config':config}
            self.store.put_index(index_id,payload)
        result={'index_id':index_id,'chunks':len(chunks),'config':config,'cached':False,'events':self.provider.events}
        self.store.trace(uuid.uuid4().hex,{'stage':'ingest','result':result,'latency_ms':(time.perf_counter()-start)*1000})
        return result
    def chroma(self,index_id):
        import chromadb
        client=chromadb.PersistentClient(path=str(Path(self.store.path).parent/'chroma'))
        return client.get_or_create_collection('idx-'+index_id,metadata={'hnsw:space':'cosine'},embedding_function=None)
    def retrieve(self,index_id,query,config='hybrid',reranker='offline',k=5):
        if config not in ('dense','hybrid','rerank'):raise ValueError('Unknown retrieval configuration')
        if not 1<=k<=50:raise ValueError('k must be 1-50')
        if not isinstance(query,str) or not 1<=len(query.strip())<=2000:raise ValueError('Question must be 1-2000 characters')
        index=self.store.get_index(index_id);chunks=index['chunks'];meta=index['config'];lookup={c['chunk_id']:c for c in chunks}
        q=self.provider.embed([query],meta['embedding'],meta['model'])[0]
        if meta['vector_store']=='chroma':
            response=self.chroma(index_id).query(query_embeddings=[q],n_results=min(50,len(chunks)),include=['distances'])
            dense=list(zip(response['ids'][0],[1-x for x in response['distances'][0]]))
        else:dense=sorted([(c['chunk_id'],cosine(q,v)) for c,v in zip(chunks,index['vectors'])],key=lambda x:(-x[1],x[0]))[:50]
        lexical=BM25(chunks).search(query,50)
        candidates=dense if config=='dense' else rrf([dense,lexical])[:50]
        if config=='rerank':candidates=self.provider.rerank(query,[lookup[cid] for cid,_ in candidates],reranker)
        return [{**lookup[cid],'score':score} for cid,score in candidates[:k]],{'dense_ids':[x[0] for x in dense],
          'bm25_ids':[x[0] for x in lexical],'config':config,'embedding':meta['embedding'],'model':meta['model'],'reranker':reranker if config=='rerank' else None}
    def ask(self,index_id,question,config='hybrid',reranker='offline',generator='offline',use_cache=True):
        if generator not in ('offline','openai','ollama'):raise ValueError('Unknown generator')
        model=os.getenv('OPENAI_MODEL') if generator=='openai' else os.getenv('OLLAMA_MODEL') if generator=='ollama' else None
        key=digest([VERSION,index_id,question,config,reranker,generator,model,os.getenv('COHERE_RERANK_MODEL')])
        start=time.perf_counter();trace_id=uuid.uuid4().hex;self.provider.events=[]
        if use_cache:
            cached=self.store.cache_get(key)
            if cached:
                cached.update({'cache_hit':True,'trace_id':trace_id,'latency_ms':round((time.perf_counter()-start)*1000,2),'events':[],'reserved_usd':0})
                self.store.trace(trace_id,cached);return cached
        try:
            with observe('rag-question',input={'question':question,'index_id':index_id},metadata={'version':VERSION}) as trace:
                began=time.perf_counter()
                with observe('retrieval',as_type='retriever',input={'query':question,'config':config}) as span:
                    chunks,retrieval=self.retrieve(index_id,question,config,reranker,5)
                    if span:span.update(output=chunks)
                retrieval_ms=round((time.perf_counter()-began)*1000,2)
                # Baseline can return irrelevant chunks: live generator must abstain from unsupported answers.
                answer=validate_answer(self.provider.answer(question,chunks,generator),chunks)
                result={'trace_id':trace_id,'index_id':index_id,'question':question,'answer':answer,'sources':chunks,
                  'retrieval':retrieval,'generator':generator,'model':model,'cache_hit':False,'version':VERSION,
                  'latency_ms':round((time.perf_counter()-start)*1000,2),'retrieval_ms':retrieval_ms,
                  'events':self.provider.events,'reserved_usd':sum(x['reserved_usd'] for x in self.provider.events),
                  'grounding':'IDs and verbatim quotes validated; semantic support still requires evaluation'}
                if trace:trace.update(output=result)
            self.store.trace(trace_id,result)
            if use_cache:self.store.cache_put(key,result)
            return result
        except Exception as exc:
            self.store.trace(trace_id,{'index_id':index_id,'stage':'failure','error_type':type(exc).__name__,'events':self.provider.events})
            raise
