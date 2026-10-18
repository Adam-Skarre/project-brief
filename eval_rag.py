"""Reproducible development evaluation; offline results are not semantic RAG results."""
import argparse,csv,json,math,statistics,tempfile,time
from pathlib import Path
from rag.pipeline import Pipeline

def metrics(ids,gold):
    hits=[int(x in gold) for x in ids]
    dcg=sum(v/math.log2(i+2) for i,v in enumerate(hits[:5]))
    ideal=sum(1/math.log2(i+2) for i in range(min(5,len(gold))))
    return {'recall_at_20':len(set(ids[:20])&gold)/len(gold),'precision_at_5':sum(hits[:5])/5,
      'mrr':next((1/(i+1) for i,v in enumerate(hits) if v),0),'ndcg_at_5':dcg/ideal if ideal else 0}

def main():
    a=argparse.ArgumentParser();a.add_argument('--embedding',choices=['offline','openai','ollama'],default='offline')
    a.add_argument('--models',nargs='+',default=['hash-v1']);a.add_argument('--sizes',nargs='+',type=int,default=[60,120,180])
    a.add_argument('--reranker',choices=['offline','cohere'],default='offline');a.add_argument('--generator',choices=['offline','openai','ollama'],default='offline')
    a.add_argument('--output',default='evaluation/retrieval_results.json');args=a.parse_args()
    questions=[json.loads(x) for x in Path('evaluation/questions.jsonl').read_text().splitlines()]
    docs=[{'name':p.name,'text':p.read_text()} for p in sorted(Path('corpus').glob('*.md'))]
    rows=[];answers=[]
    # Persistent ledger: repeating evaluations must not reset a paid request budget.
    p=Pipeline('local_data/evaluation.sqlite')
    for model in args.models:
      for size in args.sizes:
        idx=p.ingest(docs,size,min(20,size//4),args.embedding,model)['index_id'];chunks=p.store.get_index(idx)['chunks']
        for config in ['dense','hybrid','rerank']:
          values=[];times=[]
          for q in questions:
            if q['answerable']:
              gold={c['chunk_id'] for c in chunks if any(e['document']==c['document'] and e['quote'] in c['text'] for e in q['evidence'])}
              if not gold:raise ValueError('Evidence crosses a chunk boundary; revise labels or use larger chunks: '+q['id'])
              t=time.perf_counter();found,_=p.retrieve(idx,q['question'],config,args.reranker,k=50);times.append((time.perf_counter()-t)*1000)
              values.append(metrics([c['chunk_id'] for c in found],gold))
            if args.generator!='offline':
              answers.append({'id':q['id'],'answerable':q['answerable'],'config':config,'size':size,'embedding':model,
                'result':p.ask(idx,q['question'],config,args.reranker,args.generator,use_cache=False)})
          rows.append({'embedding_provider':args.embedding,'model':model,'size':size,'config':config,'reranker':args.reranker,
            'chunks':len(chunks),'questions':len(values),**{k:round(statistics.mean(v[k] for v in values),4) for k in values[0]},
            'retrieval_p95_ms':round(sorted(times)[math.ceil(.95*len(times))-1],2)})
    report={'scope':'Author-labelled development corpus; not independently reviewed. Offline vectors and reranking are lexical demonstrations.',
      'generation_evaluated':args.generator!='offline','results':rows}
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
    if answers:Path(args.output+'.answers.json').write_text(json.dumps(answers,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
