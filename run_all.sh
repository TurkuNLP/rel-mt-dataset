mkdir -p translated-completed
for fname in translated/*
do
    echo $fname
    python3 doc2json.py --out translated-completed/all all_detokenized.jsonl "$fname" 
done
