import json
import time
from pathlib import Path
from pypdf import PdfReader
from playwright.sync_api import sync_playwright

import policy
from memory import STATE, log

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
SHOTS = BASE / "logs" / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

_pw = None
_browser = None
_page = None


def close_browser():
    global _pw, _browser, _page
    try:
        if _browser:
            _browser.close()
    except Exception:
        pass
    try:
        if _pw:
            _pw.stop()
    except Exception:
        pass
    _pw = _browser = _page = None


def _get_page():
    global _pw, _browser, _page
    if _page is not None and _page.is_closed():
        close_browser()
    if _page is None:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(headless=False, slow_mo=400)
        _page = _browser.new_page()
    return _page


def _shot(label):
    path = SHOTS / f"{int(time.time())}_{label}.png"
    _get_page().screenshot(path=str(path))
    return str(path.relative_to(BASE))


def _safe_path(p):
    full = (BASE / p).resolve()
    if DATA.resolve() not in full.parents and full != DATA.resolve():
        raise ValueError("Access denied: only the data/ folder is allowed.")
    return full


def list_files(folder):
    full = _safe_path(folder)
    return json.dumps(sorted(f.name for f in full.iterdir()))


def read_pdf(path):
    full = _safe_path(path)
    reader = PdfReader(str(full))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def read_text_file(path):
    return _safe_path(path).read_text(encoding="utf-8")


def open_page(url):
    page = _get_page()
    page.goto(url)
    return f"Opened {url}. Screenshot: {_shot('open')}"


def read_page():
    page = _get_page()
    text = page.inner_text("body")
    fields = page.eval_on_selector_all(
        "input, button, select, textarea",
        "els => els.map(e => ({tag: e.tagName, name: e.name, id: e.id, "
        "type: e.type, value: e.value, text: e.innerText}))",
    )
    return json.dumps({"url": page.url, "visible_text": text, "form_elements": fields})


def fill_field(selector, value):
    page = _get_page()
    page.fill(selector, str(value), timeout=5000)
    return f"Filled {selector} with {value}"


def click(selector):
    page = _get_page()
    blocked = policy.check_click(page, selector)
    if blocked:
        return blocked
    page.click(selector, timeout=5000)
    page.wait_for_load_state()
    return f"Clicked {selector}. Screenshot: {_shot('click')}"


def ask_human(question):
    print(f"\n[AGENT NEEDS HUMAN INPUT] {question}")
    answer = input("Your answer: ")
    approved = answer.strip().lower() in ("y", "yes", "approve", "approved", "ok")
    if approved:
        STATE["approved"] = True
    log({"event": "human", "question": question, "answer": answer, "approved": approved})
    return answer


TOOL_FUNCTIONS = {
    "list_files": list_files,
    "read_pdf": read_pdf,
    "read_text_file": read_text_file,
    "open_page": open_page,
    "read_page": read_page,
    "fill_field": fill_field,
    "click": click,
    "ask_human": ask_human,
}


def _decl(name, description, props):
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
            "required": list(props.keys()),
        },
    }


TOOL_DECLARATIONS = [
    _decl("list_files", "List files in a folder inside data/.", {"folder": "e.g. data/invoices"}),
    _decl("read_pdf", "Read the text of a PDF file inside data/.", {"path": "e.g. data/invoices/ACM-1001.pdf"}),
    _decl("read_text_file", "Read a text file inside data/.", {"path": "e.g. data/company_context.md"}),
    _decl("open_page", "Open a URL in the browser.", {"url": "full URL"}),
    _decl("read_page", "Read the current page text and list its form fields, buttons and their names/ids.", {}),
    _decl("fill_field", "Type a value into a form field using a CSS selector.", {"selector": "e.g. input[name='vendor']", "value": "text to type"}),
    _decl("click", "Click an element using a CSS selector.", {"selector": "e.g. #save"}),
    _decl("ask_human", "Ask the human for approval or missing information. Waits for the answer.", {"question": "the question"}),
]