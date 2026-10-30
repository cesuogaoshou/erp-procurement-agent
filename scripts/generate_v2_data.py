import argparse
import json
from backend.app.services.dataset_v2 import DEFAULT_OUTPUT, generate, validate


def main():
    parser=argparse.ArgumentParser(description='Generate/validate autonomous simulated V2; never writes V1.')
    parser.add_argument('--output',default=str(DEFAULT_OUTPUT))
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args()
    result=validate(args.output) if args.validate_only else generate(args.output)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
