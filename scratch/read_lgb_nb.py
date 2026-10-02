import json, sys

sys.stdout.reconfigure(encoding='utf-8')
with open('training/models/07_lightgbm_ranker.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for i in range(min(19, len(nb['cells']))):
    cell = nb['cells'][i]
    print(f"=== CELL {i} ({cell['cell_type']}) ===")
    print(''.join(cell['source']))
    outputs = cell.get('outputs', [])
    if outputs:
        print("--- OUTPUTS ---")
        for out in outputs:
            if 'text' in out:
                print(''.join(out['text']))
            elif 'data' in out and 'text/plain' in out['data']:
                print(''.join(out['data']['text/plain']))
