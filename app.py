from flask import Flask, request, render_template_string
import os
import re

app = Flask(__name__)
INVOICES = []
INJECT = os.getenv("INJECT_FAILURE") == "1"
FAILED_ONCE = False

PAGE = """
<!doctype html>
<html><head><title>Company Finance System</title></head>
<body style="font-family:Arial;margin:30px">
<h1>Company Finance System</h1>
<p><a href="/">Invoice List</a> | <a href="/add">Add Invoice</a></p>
<hr>
{{ body|safe }}
</body></html>
"""

LIST_BODY = """
<h2>Saved Invoices</h2>
<table border="1" cellpadding="6" id="invoice-table">
<tr><th>Vendor</th><th>Invoice No</th><th>Amount</th><th>Due Date</th></tr>
{% for i in invoices %}
<tr><td>{{i.vendor}}</td><td>{{i.number}}</td><td>{{i.amount}}</td><td>{{i.due}}</td></tr>
{% endfor %}
</table>
"""

FORM_BODY = """
<h2>Add Invoice</h2>
{% if error %}<p id="error" style="color:red">{{error}}</p>{% endif %}
<form method="post" action="/add">
  Vendor: <input name="vendor" value="{{v.get('vendor','')}}"><br><br>
  Invoice Number: <input name="number" value="{{v.get('number','')}}"><br><br>
  Amount (INR): <input name="amount" value="{{v.get('amount','')}}"><br><br>
  Due Date (DD/MM/YYYY): <input name="due" value="{{v.get('due','')}}"><br><br>
  <button type="submit" id="save">Save Invoice</button>
</form>
"""


def render(template, **ctx):
    body = render_template_string(template, **ctx)
    return render_template_string(PAGE, body=body)


@app.route("/")
def index():
    return render(LIST_BODY, invoices=INVOICES)


@app.route("/add", methods=["GET", "POST"])
def add():
    global FAILED_ONCE
    if request.method == "GET":
        return render(FORM_BODY, error=None, v={})
    v = {k: request.form.get(k, "").strip() for k in ["vendor", "number", "amount", "due"]}
    if INJECT and not FAILED_ONCE:
        FAILED_ONCE = True
        return render(FORM_BODY, error="Temporary server error (503). Please try again.", v=v)
    if not all(v.values()):
        return render(FORM_BODY, error="All fields are required.", v=v)
    try:
        if float(v["amount"]) <= 0:
            raise ValueError
    except ValueError:
        return render(FORM_BODY, error="Amount must be a positive number.", v=v)
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", v["due"]):
        return render(FORM_BODY, error="Due date must be in DD/MM/YYYY format.", v=v)
    if any(i["number"] == v["number"] for i in INVOICES):
        return render(FORM_BODY, error="Duplicate invoice number.", v=v)
    INVOICES.append(v)
    return render(LIST_BODY, invoices=INVOICES)


@app.route("/reset")
def reset():
    INVOICES.clear()
    return "reset ok"


if __name__ == "__main__":
    app.run(port=5000, debug=False)