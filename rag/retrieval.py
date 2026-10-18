import hashlib, math, re
from collections import Counter

STOP=set('a an the is are was were how what when where which who to of in on for and or with do does can it this that i my'.split())
def tokens(text):return [x for x in re.findall(r'[a-z0-9]+(?:[-_][a-z0-9]+)*',text.lower()) if x not in STOP]

def chunk_document(name,text,size=180,overlap=35):
    if not isinstance(name,str) or not name.strip() or len(name)>200:raise ValueError('Document name must be 1-200 characters')
    if not isinstance(text,str) or not text.strip() or len(text)>250000:raise ValueError('Document text must be 1-250000 characters')
    if not 30<=size<=800 or not 0<=overlap<size:raise ValueError('Invalid word chunk size or overlap')
    # Character offsets and line numbers remain anchored to the original document.
    matches=list(re.finditer(r'\S+',text));chunks=[];doc_id=hashlib.sha256((name+'\0'+text).encode()).hexdigest()[:16]
    for start in range(0,len(matches),size-overlap):
        end=min(start+size,len(matches));a=matches[start].start();b=matches[end-1].end()
        chunks.append({'chunk_id':f'{doc_id}-{start}-{end}','document':name,'text':text[a:b],
          'start_line':text.count('\n',0,a)+1,'end_line':text.count('\n',0,b)+1,'start_char':a,'end_char':b})
        if end==len(matches):break
    return chunks

class BM25:
    def __init__(self,chunks):
        self.chunks=chunks;self.docs=[Counter(tokens(c['text'])) for c in chunks]
        self.lengths=[sum(d.values()) for d in self.docs];self.avg=sum(self.lengths)/max(len(chunks),1)
        self.df=Counter(t for d in self.docs for t in d)
    def search(self,query,k=50):
        scores=[];n=len(self.docs)
        for i,d in enumerate(self.docs):
            score=0.0
            for term in set(tokens(query)):
                tf=d[term]
                if tf:
                    idf=math.log(1+(n-self.df[term]+0.5)/(self.df[term]+0.5))
                    score+=idf*tf*2.5/(tf+1.5*(0.25+0.75*self.lengths[i]/max(self.avg,1)))
            if score>0:scores.append((self.chunks[i]['chunk_id'],score))
        return sorted(scores,key=lambda p:(-p[1],p[0]))[:k]

def hash_embedding(text,dim=256):
    """Offline lexical feature hashing, NOT a semantic/learned embedding."""
    result=[0.0]*dim
    for token,count in Counter(tokens(text)).items():
        h=int(hashlib.sha256(token.encode()).hexdigest(),16)
        result[h%dim]+=(1 if (h//dim)%2 else -1)*count
    norm=math.sqrt(sum(v*v for v in result)) or 1
    return [v/norm for v in result]

def cosine(a,b):
    if len(a)!=len(b):raise ValueError('Embedding dimensions do not match')
    denom=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b))/denom if denom else 0.0

def rrf(rankings,constant=60):
    scores={}
    for ranking in rankings:
        seen=set()
        for rank,(rid,_) in enumerate(ranking,1):
            if rid not in seen:scores[rid]=scores.get(rid,0)+1/(constant+rank);seen.add(rid)
    return sorted(scores.items(),key=lambda p:(-p[1],p[0]))

def lexical_rerank(query,chunks):
    """Offline demonstration reranker; does NOT stand in for a cross-encoder."""
    q=set(tokens(query))
    def score(c):
        t=set(tokens(c['text']));return len(q&t)/max(len(q),1)
    return sorted([(c['chunk_id'],score(c)) for c in chunks],key=lambda p:(-p[1],p[0]))
