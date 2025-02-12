#!/usr/bin/env python3
import os
import csv
from flask import (
    Flask,
    request,
    redirect,
    url_for,
    render_template_string,
    send_file,
    abort,
)

app = Flask(__name__)

CSV_PATH = os.path.join(os.getcwd(), "data", "runs.csv")
FIELDNAMES = [
    "run timestamp",
    "filename left",
    "filename right",
    "vlm output extracted number left",
    "vlm output extracted number right",
    "vlm left model name",
    "vlm right model name",
    "left ground truth",
    "right ground truth",
    "task type",
    "bad record",
]


def load_csv():
    if not os.path.exists(CSV_PATH):
        raise Exception(f"CSV file not found:\n{CSV_PATH}")
    with open(CSV_PATH, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        recs = list(reader)
    return recs


def save_csv():
    try:
        with open(CSV_PATH, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(records)
        return True
    except Exception as e:
        print(f"Failed to save CSV:\n{e}")
        return False


records = load_csv()


def get_display_records():
    # Exclude records marked as bad.
    filtered = [
        r
        for r in records
        if r.get("bad record", "").strip().lower() not in ("true", "1", "yes")
    ]
    # Sort by run timestamp descending.
    sorted_by_timestamp = sorted(
        filtered, key=lambda r: r["run timestamp"], reverse=True
    )
    # Then, put records with empty right ground truth first (stable sort).
    return sorted(
        sorted_by_timestamp, key=lambda r: bool(r["right ground truth"].strip())
    )


@app.route("/", methods=["GET", "POST"])
def index():
    display_records = get_display_records()
    if not display_records:
        return render_template_string("<p>No records found in CSV.</p>")

    try:
        idx = int(request.args.get("index", "0"))
    except ValueError:
        idx = 0
    if idx < 0:
        idx = 0
    if idx >= len(display_records):
        idx = len(display_records) - 1

    if request.method == "POST":
        action = request.form.get("action")
        try:
            idx = int(request.form.get("index", "0"))
        except ValueError:
            idx = 0
        display_records = get_display_records()
        if not display_records:
            return render_template_string("<p>No records found in CSV.</p>")
        if idx < 0:
            idx = 0
        if idx >= len(display_records):
            idx = len(display_records) - 1

        record = display_records[idx]
        record["left ground truth"] = request.form.get("left_ground_truth", "")
        record["right ground truth"] = request.form.get("right_ground_truth", "")
        record["bad record"] = (
            "True" if request.form.get("bad_record") == "on" else "False"
        )

        if action == "prev":
            if idx > 0:
                idx -= 1
        elif action == "next":
            if idx < len(display_records) - 1:
                idx += 1
            save_csv()
        elif action == "save":
            save_csv()
        elif action == "quit":
            save_csv()
            return render_template_string(
                "<p>CSV file saved successfully. You may now close your browser.</p>"
            )
        return redirect(url_for("index", index=idx))

    record = display_records[idx]
    left_path = record.get("filename left", "")
    right_path = record.get("filename right", "")
    left_img_url = (
        url_for("serve_image", path=left_path)
        if left_path and os.path.exists(left_path)
        else None
    )
    right_img_url = (
        url_for("serve_image", path=right_path)
        if right_path and os.path.exists(right_path)
        else None
    )

    template = """
    <!doctype html>
    <html>
    <head>
      <title>Runs CSV Labeling Tool</title>
    </head>
    <body>
      <h1>Record {{ idx + 1 }} of {{ total }}</h1>
      {% set non_gt_fields = [] %}
      {% for field in fields %}
        <p><strong>{{ field }}:</strong> {{ record[field] }}</p>
      {% endfor %}
      <form method="post">
        <input type="hidden" name="index" value="{{ idx }}">
        <p>
          <label>left ground truth:</label>
          <input type="text" name="left_ground_truth" value="{{ record['left ground truth'] }}">
        </p>
        <p>
          <label>right ground truth:</label>
          <input type="text" name="right_ground_truth" value="{{ record['right ground truth'] }}">
        </p>
        <p>
          <label>Bad record:</label>
          <input type="checkbox" name="bad_record" {% if record['bad record']|lower in ['true', '1', 'yes'] %}checked{% endif %}>
        </p>
        <div style="display: flex; justify-content: space-around;">
          <div>
            {% if left_img_url %}
              <img src="{{ left_img_url }}" style="max-width:400px; max-height:400px;">
            {% else %}
              <p>Left image not found</p>
            {% endif %}
          </div>
          <div>
            {% if right_img_url %}
              <img src="{{ right_img_url }}" style="max-width:400px; max-height:400px;">
            {% else %}
              <p>Right image not found</p>
            {% endif %}
          </div>
        </div>
        <p>
          <button type="submit" name="action" value="prev">Previous</button>
          <button type="submit" name="action" value="save">Save</button>
          <button type="submit" name="action" value="next">Next</button>
          <button type="submit" name="action" value="quit">Quit</button>
        </p>
      </form>
    </body>
    </html>
    """
    # Exclude ground truth and bad record fields from the header display.
    non_gt_fields = [
        f
        for f in FIELDNAMES
        if f not in ["left ground truth", "right ground truth", "bad record"]
    ]
    return render_template_string(
        template,
        record=record,
        idx=idx,
        total=len(display_records),
        fields=non_gt_fields,
        left_img_url=left_img_url,
        right_img_url=right_img_url,
    )


@app.route("/image")
def serve_image():
    path = request.args.get("path")
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path)


if __name__ == "__main__":
    app.run(debug=True)
