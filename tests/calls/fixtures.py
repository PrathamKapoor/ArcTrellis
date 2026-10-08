"""Small mixed repository with independent success and uncertainty cases."""


def mixed_sources():
    return {
        "util.py": "def validate():\n    pass\n",
        "service.py": (
            "from util import validate\ndef helper():\n    pass\ndef create():\n"
            "    validate()\n    helper()\ndef duplicate(): pass\ndef duplicate(): pass\n"
            "duplicate()\nmissing()\nobj[key]()\n"
        ),
        "util.ts": "export function audit() {}",
        "service.ts": 'import { audit } from "./util";\nexport function submit() { audit(); }',
        "helper.js": "export function sanitize() {}",
        "app.js": 'import * as helper from "./helper";\nfunction run() { helper.sanitize(); }',
    }
