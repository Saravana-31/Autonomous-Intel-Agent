import os
import sys
# Ensure backend package dir is on path
ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from tiered_extractor import TieredExtractor
from post_extraction_validator import validate_profile, ExtractionValidationError

DATA_DIR = os.path.join('data', 'ayadata.ai')
HTML_FILENAME = 'ayadata.ai.html'

if __name__ == '__main__':
    path = os.path.join(DATA_DIR, HTML_FILENAME)
    if not os.path.exists(path):
        print('HTML snapshot not found at', path)
        sys.exit(1)

    with open(path, 'r', encoding='utf-8') as fh:
        html = fh.read()

    extractor = TieredExtractor()
    profile = extractor.extract(text=html, company_domain='ayadata.ai', html_files=[(HTML_FILENAME, html)])

    # Write profile to stdout and cache (support pydantic v1 and v2)
    print('--- Extracted CompanyProfile ---')
    try:
        # pydantic v2
        print(profile.model_dump_json(indent=2, ensure_ascii=False))
    except Exception:
        try:
            # pydantic v1
            print(profile.json(indent=2, ensure_ascii=False))
        except Exception:
            # fallback: dump dict
            import json
            print(json.dumps(profile.model_dump() if hasattr(profile, 'model_dump') else profile.dict(), indent=2, ensure_ascii=False))

    # Run validator
    try:
        validate_profile(profile)
        print('\nValidation: OK')
    except ExtractionValidationError as e:
        print('\nValidation: FAILED')
        print(str(e))

    # Exit with code 0 on success, 2 on failure
    try:
        validate_profile(profile)
        sys.exit(0)
    except ExtractionValidationError:
        sys.exit(2)
