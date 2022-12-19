import json
import sys
import sacremoses
import re

dt=sacremoses.MosesDetokenizer(lang='en')

def detokenize_and_align(tokens):
    alignment=[]
    detokenized=dt.detokenize(tokens)
    detokenized=re.sub(r"\s('?(s|t|nt|n))\b",r"\1",detokenized)
    
    token_idx=0
    char_idx=0
    while char_idx < len(detokenized):
        if detokenized[char_idx]==" ":
            char_idx+=1
            continue
        if not detokenized[char_idx:].startswith(tokens[token_idx]):
            print(detokenized[char_idx:])
            print(tokens[token_idx])
            assert False
        alignment.append((char_idx,char_idx+len(tokens[token_idx])))
        char_idx+=len(tokens[token_idx])
        token_idx+=1
    assert len(alignment)==len(tokens)
    for token,span in zip(tokens,alignment):
        assert token==detokenized[span[0]:span[1]]
    return detokenized,alignment
        
### {'doc_key': 'ai-train-99', 'sentence': ['59', ',', 'pp.', '2547-2553', ',', 'Oct.', '2011', 'In', 'one', 'dimensional', 'polynomial-based', 'memory', '(', 'or', 'memoryless', ')', 'DPD', ',', 'in', 'order', 'to', 'solve', 'for', 'the', 'digital', 'pre-distorter', 'polynomials', 'coefficients', 'and', 'minimize', 'the', 'mean', 'squared', 'error', '(', 'MSE', ')', ',', 'the', 'distorted', 'output', 'of', 'the', 'nonlinear', 'system', 'must', 'be', 'over-sampled', 'at', 'a', 'rate', 'that', 'enables', 'the', 'capture', 'of', 'the', 'nonlinear', 'products', 'of', 'the', 'order', 'of', 'the', 'digital', 'pre-distorter', '.'], 'ner': [[8, 11, 'misc'], [16, 16, 'misc'], [31, 33, 'metrics'], [35, 35, 'metrics']], 'relations': [[35, 35, 31, 33, 'named', '', False, False]]}


for line in sys.stdin:
    doc=json.loads(line)
    detokenized,alignment=detokenize_and_align(doc["sentence"])
    doc["sentence-detokenized"]=detokenized
    doc["token2charspan"]=alignment
    print(json.dumps(doc,ensure_ascii=False,sort_keys=True))
    
    
