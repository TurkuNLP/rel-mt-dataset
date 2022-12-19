import json
import argparse

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('SRC', help='source json file with detokenized data included')
    parser.add_argument('TGT', help='target json file')
    args = parser.parse_args()

    
    for doc_src,doc_tgt in zip(open(args.SRC),open(args.TGT)):
        doc_src=json.loads(doc_src)
        doc_tgt=json.loads(doc_tgt)
        print(doc_src["sentence-detokenized"])
        print()
        print(doc_tgt["sentence-detokenized"])
        print()
        for src_ner_idx,tgt_ner in zip(doc_tgt["ner_mapping_to_source"],doc_tgt["ner"]):
            src_ner=doc_src["ner"][src_ner_idx]
            src_ner_txt=" ".join(doc_src["sentence"][src_ner[0]:src_ner[1]+1])
            tgt_ner_txt=" ".join(doc_tgt["sentence"][tgt_ner[0]:tgt_ner[1]+1])
            print(src_ner[2],"    ",src_ner_txt,"     ",tgt_ner_txt)
        print()
        print()
        print("-"*80)
        print()
        print()
        
