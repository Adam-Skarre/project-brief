"""Export generation review sheets and measure human/judge agreement. No fabricated labels."""
import argparse,csv,json
from pathlib import Path

def kappa(a,b):
    if not a or len(a)!=len(b):raise ValueError('Paired nonempty labels required')
    observed=sum(x==y for x,y in zip(a,b))/len(a)
    expected=sum(a.count(v)*b.count(v) for v in set(a+b))/len(a)**2
    return None if expected==1 else (observed-expected)/(1-expected)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['export','score']);parser.add_argument('path');parser.add_argument('--output',default='evaluation/generation_review.csv');a=parser.parse_args()
    if a.mode=='export':
      records=json.loads(Path(a.path).read_text())
      with open(a.output,'w',newline='') as f:
        fields=['id','config','size','embedding','answerable','question','answer','sources','human_grounded','judge_grounded','human_relevant','judge_relevant','human_hallucinated','judge_hallucinated','notes']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for x in records:w.writerow({**{k:x[k] for k in fields[:5]},'question':x['result']['question'],'answer':json.dumps(x['result']['answer']),'sources':json.dumps(x['result']['sources'])})
    else:
      rows=list(csv.DictReader(open(a.path)));out={}
      for field in ['grounded','relevant','hallucinated']:
        human=[r['human_'+field] for r in rows if r['human_'+field] in ('0','1')]
        pairs=[(r['human_'+field],r['judge_'+field]) for r in rows if r['human_'+field] in ('0','1') and r['judge_'+field] in ('0','1')]
        out[field]={'human_label_count':len(human),'human_positive_rate':sum(map(int,human))/len(human) if human else None,'paired_count':len(pairs),'cohen_kappa':kappa([x for x,y in pairs],[y for x,y in pairs]) if pairs else None}
      print(json.dumps(out,indent=2))
if __name__=='__main__':main()
