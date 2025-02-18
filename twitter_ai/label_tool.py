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
    "first_scale_value",  # New field for 'length' task type
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


def get_display_records(task_filter=None):
    filtered = [
        r
        for r in records
        if (r.get("bad record") or "").strip().lower() not in ("true", "1", "yes")
    ]
    if task_filter:
        filtered = [r for r in filtered if r.get("task type", "") in task_filter]
    sorted_by_timestamp = sorted(
        filtered, key=lambda r: r["run timestamp"], reverse=True
    )
    return sorted(
        sorted_by_timestamp, key=lambda r: bool(r["right ground truth"].strip())
    )


def get_stats(task_type):
    task = task_type.strip().lower()
    total = 0
    labeled = 0
    for r in records:
        if r.get("task type", "").strip().lower() == task:
            total += 1
            if task == "length":
                if (
                    r.get("right ground truth", "").strip()
                    and r.get("first_scale_value", "").strip()
                ):
                    labeled += 1
            else:
                if (
                    r.get("left ground truth", "").strip()
                    and r.get("right ground truth", "").strip()
                ):
                    labeled += 1
    return labeled, total


@app.route("/", methods=["GET", "POST"])
def index():
    # Get current filter from GET or POST values.
    current_filter = request.values.getlist("filter_task_type")
    display_records = get_display_records(
        task_filter=current_filter if current_filter else None
    )
    if not display_records:
        return render_template_string("<p>No records found in CSV.</p>")

    try:
        idx = int(request.values.get("index", "0"))
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
        display_records = get_display_records(
            task_filter=current_filter if current_filter else None
        )
        if not display_records:
            return render_template_string("<p>No records found in CSV.</p>")
        if idx < 0:
            idx = 0
        if idx >= len(display_records):
            idx = len(display_records) - 1

        record = display_records[idx]
        record["left ground truth"] = request.form.get("left_ground_truth", "")
        record["right ground truth"] = request.form.get("right_ground_truth", "")
        record["task type"] = request.form.get("task_type", "")
        record["bad record"] = (
            "True" if request.form.get("bad_record") == "on" else "False"
        )

        # Update first_scale_value if task type is 'length'
        if record["task type"].strip().lower() == "length":
            record["first_scale_value"] = request.form.get("first_scale_value", "")

        # Propagate ground truth updates to all records with the same filenames.
        left_filename = record.get("filename left", "")
        right_filename = record.get("filename right", "")
        for r in records:
            if left_filename and r.get("filename left", "") == left_filename:
                r["left ground truth"] = record["left ground truth"]
            if right_filename and r.get("filename right", "") == right_filename:
                r["right ground truth"] = record["right ground truth"]

        # Propagate task type updates (and first_scale_value for 'length') to all records with the same run timestamp.
        timestamp = record.get("run timestamp", "")
        for r in records:
            if r.get("run timestamp", "") == timestamp:
                r["task type"] = record["task type"]
                if record["task type"].strip().lower() == "length":
                    r["first_scale_value"] = record.get("first_scale_value", "")

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
        return redirect(url_for("index", index=idx, filter_task_type=current_filter))

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

    # Compute distinct task types for the filter checklist.
    task_types = sorted(
        {
            r.get("task type", "").strip()
            for r in records
            if r.get("task type", "").strip()
        }
    )

    # Compute labeling statistics for current task type.
    current_task = record.get("task type", "").strip()
    if current_task:
        task_labeled, task_total = get_stats(current_task)
    else:
        task_labeled, task_total = 0, 0

    template = """
    <!doctype html>
    <html>
    <head>
      <title>Runs CSV Labeling Tool</title>
      <style>
        .images-container {
          display: flex;
          justify-content: flex-start;
          gap: 4px;
        }
        .images-container img {
          max-width: 400px;
          max-height: 400px;
        }
      </style>
    </head>
    <body>
      <form method="get">
        <fieldset>
          <legend>Filter by Task Type</legend>
          {% for t in task_types %}
            <label>
              <input type="checkbox" name="filter_task_type" value="{{ t }}" {% if t in current_filter %}checked{% endif %}>
              {{ t }}
            </label>
          {% endfor %}
        </fieldset>
        <button type="submit">Apply Filter</button>
      </form>
      <h1>Record {{ idx + 1 }} of {{ total }}</h1>
      {% if record['task type'] %}
        <p>Statistics for "{{ record['task type'] }}": Labeled {{ task_labeled }} out of {{ task_total }}</p>
      {% endif %}
      {% for field in fields %}
        <p><strong>{{ field }}:</strong> {{ record[field] }}</p>
      {% endfor %}
      <form id="labeling-form" method="post">
        <input type="hidden" name="index" value="{{ idx }}">
        {% for t in current_filter %}
          <input type="hidden" name="filter_task_type" value="{{ t }}">
        {% endfor %}
        <!-- Images container moved above input fields -->
        <div class="images-container">
          <div>
            {% if left_img_url %}
              <img src="{{ left_img_url }}">
            {% else %}
              <p>Left image not found</p>
            {% endif %}
          </div>
          <div>
            {% if right_img_url %}
              <img src="{{ right_img_url }}">
            {% else %}
              <p>Right image not found</p>
            {% endif %}
          </div>
        </div>
        <p>
          <label>left ground truth:</label>
          <input type="text" name="left_ground_truth" value="{{ record['left ground truth'] or record['vlm output extracted number left'] }}">
        </p>
        <p>
          <label>right ground truth:</label>
          <input type="text" name="right_ground_truth" value="{{ record['right ground truth'] }}">
        </p>
        <p>
          <label>Task type:</label>
          <input type="text" name="task_type" value="{{ record['task type'] }}">
        </p>
        {% if record['task type']|lower == 'length' %}
        <p>
          <label>First scale value:</label>
          <input type="text" name="first_scale_value" value="{{ record.get('first_scale_value', '') }}">
        </p>
        {% endif %}
        <p>
          <label>Bad record:</label>
          <input type="checkbox" name="bad_record" {% if record['bad record']|lower in ['true', '1', 'yes'] %}checked{% endif %}>
        </p>
        <p>
          <button type="submit" name="action" value="prev">Previous</button>
          <button type="submit" name="action" value="save">Save</button>
          <button type="submit" name="action" value="next">Next</button>
          <button type="submit" name="action" value="quit">Quit</button>
        </p>
        <script>
          document.addEventListener("DOMContentLoaded", function() {
            var form = document.getElementById("labeling-form");
            form.addEventListener("keydown", function(e) {
              if (e.key === "Enter") {
                e.preventDefault();
                form.querySelector("button[name='action'][value='next']").click();
              }
            });
          });
        </script>
      </form>
    </body>
    </html>
    """
    non_gt_fields = [
        f
        for f in FIELDNAMES
        if f
        not in ["left ground truth", "right ground truth", "bad record", "task type"]
    ]
    return render_template_string(
        template,
        record=record,
        idx=idx,
        total=len(display_records),
        fields=non_gt_fields,
        left_img_url=left_img_url,
        right_img_url=right_img_url,
        task_types=task_types,
        current_filter=current_filter,
        task_labeled=task_labeled,
        task_total=task_total,
    )


@app.route("/image")
def serve_image():
    path = request.args.get("path")
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path)


if __name__ == "__main__":
    app.run(debug=True)
