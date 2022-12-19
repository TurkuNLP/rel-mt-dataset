import os
import docx
import argparse
import json
import ufal.udpipe as udpipe
import re
import sys
import unicodedata

def index_fonts():
    palette=[]
    with open("palette.txt") as f:
        for line in f:
            line=line.strip()
            if not line.startswith("#"):
                continue
            palette.append(line)
    #print(palette)
    assert len(palette)==len(set(palette))

    rgb_colors=[]
    for colorspec in palette:
        color=docx.shared.RGBColor.from_string(colorspec[1:].upper())
        rgb_colors.append(color)

    return rgb_colors

rgb_colors=index_fonts()

def yield_translations(wdoc):
    for i,para in enumerate(wdoc.paragraphs):
        if not para.runs:
            print("EMPTY",i,file=sys.stderr)
            yield ("XXX",[])
            continue
        if para.runs[0].bold:
            #we have a new document
            pass
        else:
            entities=[]
            txt=""
            for r in para.runs:
                if r.font.color.rgb in rgb_colors: #this is an entity
                    entities.append((rgb_colors.index(r.font.color.rgb),len(txt),len(txt)+len(r.text)))
                    txt+=r.text
                else: #this is a normal span
                    txt+=r.text
            assert txt==para.text
            yield txt, entities

def get_token_offsets(sent,tokenizer):
    tokenized=tokenizer.process(sent)
    offset_matches=list(re.finditer("TokenRange=([0-9]+):([0-9]+)",tokenized))
    tokens=list((int(m.group(1)),int(m.group(2))) for m in offset_matches)
    #I know this is silly hack but let's make a simple char-offset -> token idx lookup, that way I can translate everything ridiculously easily
    charidx2tokenidx=[0 for _ in range(tokens[-1][-1])] #zeros all the way to the last token
    for tokeni,(b,e) in enumerate(tokens):
        for i in range(b,tokens[-1][-1]):
            charidx2tokenidx[i]=tokeni
    
    return tokens,charidx2tokenidx


def get_trailing_punct(s,stop_at=""):
    #returns index into s from which s only contains punctuation
    #stop_at is a list of chars which should be considered a block beyond which the search stops
    #this will have the punctuation characters from the orig entity, so that we do not trim such punctuation
    #which is actually found in the original text
    for i in range(len(s)-1,-1,-1):
        cat=unicodedata.category(s[i])
        if cat[0]=="L" or cat[0]=="N" or cat[0]=="S" or s[i] in stop_at:
            #a letter, number, or symbol
            return i+1
    else:
        return 0     
            

def trim_trailing_punct(orig_entity,transl_entity):
    #this is quite crude but hope it does the trick
    orig_punct_i=get_trailing_punct(orig_entity)
    orig_punct=orig_entity[orig_punct_i:] #this will be quite often simply an empty string if there is no punct
    transl_punct_i=get_trailing_punct(transl_entity,orig_punct)
    return transl_punct_i


    

if __name__=="__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    #parser.add_argument("--udpipe-model",help="UDpipe model file used in tokenization")
    parser.add_argument('SRC', help='source json file with detokenized data included')
    parser.add_argument('DOC', help='The translated docx')
    parser.add_argument('--outfileprefix', help='Prefix for outfile, will be completed with _lang.docx; if not given, the output will go to stdout')
    args = parser.parse_args()

    lang2ud={} #fi -> finnish-tdt  ... maps lang codes into Udpipe model names
    with open("lang2ud.csv","rt") as f:
        for line in f:
            line=line.strip()
            lang,ud=line.split()
            lang2ud[lang]=ud

    #assume that DOC comes from DeepL in which case it will be "whatevername<space>lang.docx"
    lang=re.match("^.* ([a-z]{2}(-[A-Z]{2})?)\.docx$",os.path.basename(args.DOC)).group(1)
    udpipe_model_name=f"udpipe/{lang2ud[lang]}-ud-2.5-191206.udpipe"
    print(f"Using udpipe model {udpipe_model_name}",file=sys.stderr)
    
    
    udpipemodel=udpipe.Model.load(udpipe_model_name)
    tokenizer=udpipe.Pipeline(udpipemodel,"tokenizer=ranges","none","none","conllu")

    src_docs=[json.loads(line) for line in open(args.SRC)]
    texts_and_entities=list(yield_translations(docx.Document(args.DOC)))
    assert len(src_docs)==len(texts_and_entities),(len(src_docs),len(texts_and_entities))
    if args.outfileprefix:
        fout=open(f"{args.outfileprefix}_{lang}_{lang2ud[lang].split('-')[0]}.jsonl","wt")
    else:
        fout=sys.stdout
    for src_doc, (translated_text,entities) in zip (src_docs,texts_and_entities):
        new_doc={}
        new_doc["doc_key"]=src_doc["doc_key"]
        new_doc["sentence-detokenized"]=translated_text
        new_doc["token2charspan"],charidx2tokenidx=get_token_offsets(translated_text,tokenizer)
        new_doc["sentence"]=list(translated_text[b:e] for b,e in new_doc["token2charspan"])
        ner=[]
        ner_mapping_to_orig=[]
        rel_mapping_to_orig=[]
        orig_ent_to_new_ent={} # (tokidx,tokidx) -> (tokidx,tokidx) from orig to new

        #now, watch out, some entities may have become broken into several pieces, we better piece them together!
        assembled_entities={} #orig_idx -> list of (b,e)
        for orig_idx,b,e in entities:
            assembled_entities.setdefault(orig_idx,[]).append((b,e))
        for lst in assembled_entities.values():
            lst.sort()
        for orig_idx,span_list in sorted(assembled_entities.items()): #go over the translated entities
            #orig_idx binds it to the orig data
            ner_mapping_to_orig.append(orig_idx)
            orig_ent=src_doc["ner"][orig_idx]
            b=span_list[0][0] #take everything
            e=span_list[-1][1]
            orig_ent_text="".join(src_doc["sentence"][orig_ent[0]:orig_ent[1]+1]) #I leave spaces out on purpose here, so they don't mess with the punctuation stripping algo
            tr_ent_text=new_doc["sentence-detokenized"][b:e]
            i=trim_trailing_punct(orig_ent_text,tr_ent_text)
            if i>0 and i<len(tr_ent_text): #we do trim!
                e-=len(tr_ent_text)-i
            #print(orig_ent_text,"     ",tr_ent_text,"    ->    ",new_doc["sentence-detokenized"][b:e],file=sys.stderr)
            new_ent=(charidx2tokenidx[b],charidx2tokenidx[e-1],orig_ent[2]) #translate the indices to tokens, recover the entity types
            orig_ent_to_new_ent[(orig_ent[0],orig_ent[1])]=(new_ent[0],new_ent[1])
            ner.append(new_ent)
        new_doc["ner"]=ner
        new_doc["ner_mapping_to_source"]=ner_mapping_to_orig #this allows us to go back to the source entities
        #whew, now the relations
        relations=[]
        for reli,(b1,e1,b2,e2,A,B,C,D) in enumerate(src_doc["relations"]): #ha ha I dont know what these four values of relation are :D, let them be ABCD
            #Can I transfer?
            (new_b1,new_e1)=orig_ent_to_new_ent.get((b1,e1),(None,None))
            (new_b2,new_e2)=orig_ent_to_new_ent.get((b2,e2),(None,None))
            if (new_b1,new_e1)==(None,None) or (new_b2,new_e2)==(None,None):
                continue #damn!
            relations.append((new_b1,new_e1,new_b2,new_e2,A,B,C,D))
            rel_mapping_to_orig.append(reli)
        new_doc["relations"]=relations
        new_doc["relations_mapping_to_source"]=rel_mapping_to_orig
        print(json.dumps(new_doc,ensure_ascii=False,sort_keys=True),file=fout)
    if fout!=sys.stdout:
        fout.close()
        
        
#{"doc_key": "ai-train-1", "sentence": ["Popular", "approaches", "of", "opinion-based", "recommender", "system", "utilize", "various", "techniques", "including", "text", "mining", ",", "information", "retrieval", ",", "sentiment", "analysis", "(", "see", "also", "Multimodal", "sentiment", "analysis", ")", "and", "deep", "learning", "X.Y.", "Feng", ",", "H.", "Zhang", ",", "Y.J.", "Ren", ",", "P.H.", "Shang", ",", "Y.", "Zhu", ",", "Y.C.", "Liang", ",", "R.C.", "Guan", ",", "D.", "Xu", ",", "(", "2019", ")", ",", ",", "21", "(", "5", ")", ":", "e12957", "."], "ner": [[3, 5, "product"], [10, 11, "field"], [13, 14, "task"], [16, 17, "task"], [21, 23, "task"], [26, 27, "field"], [28, 29, "researcher"], [31, 32, "researcher"], [34, 35, "researcher"], [37, 38, "researcher"], [40, 41, "researcher"], [43, 44, "researcher"], [46, 47, "researcher"], [49, 50, "researcher"]], "relations": [[3, 5, 10, 11, "part-of", "", false, false], [3, 5, 10, 11, "usage", "", false, false], [3, 5, 13, 14, "part-of", "", false, false], [3, 5, 13, 14, "usage", "", false, false], [3, 5, 16, 17, "part-of", "", false, false], [3, 5, 16, 17, "usage", "", false, false], [3, 5, 26, 27, "part-of", "", false, false], [3, 5, 26, 27, "usage", "", false, false], [21, 23, 16, 17, "part-of", "", false, false], [21, 23, 16, 17, "type-of", "", false, false]]}
