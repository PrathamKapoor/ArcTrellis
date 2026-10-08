"""Synthetic mixed HTTP repository used by tests and the local smoke command."""


def http_sources():
    return {
        "fastapi_app.py": (
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "def validate_payment():\n    pass\n"
            '@app.post("/payments")\n'
            "async def create_payment():\n    validate_payment()\n"
        ),
        "flask_app.py": (
            "from flask import Flask\napp = Flask(__name__)\n"
            '@app.route("/health", methods=["GET", "POST"])\n'
            "def health():\n    return 'ok'\n"
        ),
        "express_app.ts": (
            'import express from "express";\n'
            'import { serve as importedHandler } from "./handlers";\n'
            "const app = express();\n"
            "function sanitize() {}\n"
            "function getUsers() { sanitize(); }\n"
            "function duplicate() {}\nfunction duplicate() {}\n"
            'app.get("/users", getUsers);\n'
            'app.post("/imported", importedHandler);\n'
            'app.get("/unknown", missing);\n'
            'app.delete("/ambiguous", duplicate);\n'
        ),
        "handlers.ts": "export function serve() {}\n",
    }
