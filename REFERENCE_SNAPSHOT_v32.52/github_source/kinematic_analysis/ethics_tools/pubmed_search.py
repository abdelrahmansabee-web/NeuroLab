import requests

url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
term = 'smartphone[Title/Abstract] AND accelerometer[Title/Abstract] AND stroke[Title/Abstract] AND ("upper limb"[Title/Abstract] OR "upper extremity"[Title/Abstract])'
params = {'db': 'pubmed', 'term': term, 'retmode': 'json', 'retmax': 20}
resp = requests.get(url, params=params, timeout=30)
ids = resp.json()['esearchresult']['idlist']
print('ids', ids)
for pmid in ids:
    s = requests.get(
        'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',
        params={'db': 'pubmed', 'id': pmid, 'retmode': 'json'},
        timeout=30,
    ).json()['result'][pmid]
    print(s['title'])
    print(s.get('source'), s.get('pubdate'), 'PMID:', pmid)
    print('---')
