import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# ensure project root is on sys.path so `backend` package is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# load .env from project root
load_dotenv(PROJECT_ROOT / '.env')

print('--- Environment ---')
print('OPENAI_API_KEY present:', bool(os.getenv('OPENAI_API_KEY')))
print('OPENAI_MODEL:', os.getenv('OPENAI_MODEL'))

print('\n--- Analyzer Info ---')
try:
    from backend.llm_analyzer import ask_gemini, analyze_score, model_source
    print('model_source:', model_source)
except Exception as e:
    print('Failed importing llm_analyzer:', e)
    raise

print('\n--- Raw LLM Reply (ask_gemini) ---')
try:
    reply = ask_gemini('Say hello in one sentence.')
    print(reply)
except Exception as e:
    print('ask_gemini error:', e)

print('\n--- analyze_score output ---')
try:
    sample = 'Experienced Python developer with 5 years in web backend, AWS, and SQL.'
    out = analyze_score(sample)
    print(json.dumps(out, indent=2))
except Exception as e:
    print('analyze_score error:', e)

print('\n--- Last llm_analyzer_debug.log lines ---')
logp = Path(__file__).parents[1] / 'backend' / 'llm_analyzer_debug.log'
if logp.exists():
    try:
        with open(logp, 'r', encoding='utf-8') as fh:
            lines = fh.read().splitlines()
        for l in lines[-30:]:
            print(l)
    except Exception as e:
        print('Error reading log:', e)
else:
    print('No debug log found at', logp)
