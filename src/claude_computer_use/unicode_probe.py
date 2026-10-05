"""Controlled, opt-in Windows Unicode probe; all CLI output is ASCII JSON."""
import argparse
import hashlib
import json
from .worker import WorkerClient

# ASCII source ensures PowerShell/console encodings cannot replace the test CJK.
PROBE_TEXT = 'caf\u00e9 \u65e5\u672c\u8a9e \U0001f600\nsecond line\ttab'

CASES = {
    'mixed': PROBE_TEXT,
    'ascii-distinct': 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
    'ascii-repeat': 'aabbccddeeff112233445566',
    'cjk': '\u65e5\u672c\u8a9e \u8a9e\u672c\u65e5 \u65e5\u65e5\u672c\u672c\u8a9e\u8a9e',
    'emoji': '\U0001f600\U0001f642\U0001f680 \U0001f600\U0001f600\U0001f642\U0001f642',
}


def payload_description(text):
    raw = text.encode('utf-16-le')
    return {'utf8_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'codepoints':[f'U+{ord(c):04X}' for c in text],
            'utf16_units':[f'{int.from_bytes(raw[i:i+2],"little"):04X}' for i in range(0,len(raw),2)]}


def main():
    parser=argparse.ArgumentParser(description='Opt-in probe on a disposable EMPTY Windows editor. Captures editor text in the report.')
    parser.add_argument('--window-id',required=True)
    parser.add_argument('--mode',choices=['observe','batch','paced'],default='observe')
    parser.add_argument('--case',choices=list(CASES),default='mixed')
    parser.add_argument('--confirm-empty-editor',action='store_true')
    args=parser.parse_args()
    if args.mode!='observe' and not args.confirm_empty_editor:
        parser.error('Mutation needs --confirm-empty-editor and a disposable empty editor')
    client=WorkerClient(timeout=12)
    try:
        client.call('bind_window',{'window_id':args.window_id})
        # No auto activation: operator must focus the test editor before running.
        report=client.call('unicode_probe',{'mode':args.mode,'confirm_empty_editor':args.confirm_empty_editor,'case':args.case})
        report['caller_fixed_payload']=payload_description(CASES[args.case])
        report['caller_worker_payload_match']=report['caller_fixed_payload']==report['fixed_payload']
        print(json.dumps(report,ensure_ascii=True,indent=2))
    finally:client.cancel()


if __name__=='__main__':main()
