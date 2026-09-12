import json,hashlib,itertools
p='w08_public_runner/w08_company_code_universe_v1.json'
d=json.load(open(p))
expected={'all':('24eb2336ea71fcec65747ffc7856974528474919f8971b452f08ccd3eb983bd2',2436),'pre':('2fc67794c6e8c94f8eabbecbd4efcf0ef4214261715a5860d51ae6f7555590dc',1281)}
for key,arrkey in [('all','all_numeric_4digit_codes'),('pre','pre_20050505_codes')]:
    arr=d[arrkey]
    b=('\n'.join(arr)+'\n').encode()
    h=hashlib.sha256(b).hexdigest()
    exp,n=expected[key]
    print(key,'len',len(arr),'unique',len(set(arr)),'sha',h,'expected',exp,'sorted',arr==sorted(arr))
    if h==exp:
        print(key,'PASS exact')
        continue
    if len(arr)==n-1 and len(set(arr))==len(arr):
        s=set(arr)
        found=[]
        for i in range(10000):
            c=f'{i:04d}'
            if c in s: continue
            cand=sorted(arr+[c])
            if hashlib.sha256(('\n'.join(cand)+'\n').encode()).hexdigest()==exp:
                found.append(c)
        print(key,'missing_candidates',found)
    elif len(arr)==n and len(set(arr))==len(arr):
        # one-extra/one-missing repair search using digest; bounded 10k*len is large, so first report only
        print(key,'same-count-digest-mismatch; manual/second-stage needed')
