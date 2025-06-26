import os
import subprocess
import requests
import base64
import json
from flask import Flask, request
from google.cloud import storage

DEST_BUCKET = os.environ.get("DEST_BUCKET")
QUARANTINE_BUCKET = os.environ.get("QUARANTINE_BUCKET")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK")

app = Flask(__name__)

def download_virus_definitions():
    subprocess.run(['/usr/bin/freshclam', '--datadir=/tmp', '--log=/tmp/freshclam.log'], check=True)

def scan_file(file_path):
    result = subprocess.run(['/usr/bin/clamscan', '-d', '/tmp', file_path], capture_output=True)
    return result.returncode, result.stdout.decode()

def send_slack_alert(filename, scan_output, quarantine_path):
    payload = {
        "text": (
            f":rotating_light: *Malware detected!*\n"
            f"File: `{filename}`\n"
            f"Moved to quarantine bucket: `{quarantine_path}`\n"
            f"Scan Output:\n```{scan_output}```"
        )
    }
    try:
        requests.post(SLACK_WEBHOOK, json=payload)
    except Exception as e:
        print(f"Failed to send Slack notification: {e}")

def process_file(event):
    bucket_name = event['bucket']
    blob_name = event['name']
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    temp_file = f"/tmp/{os.path.basename(blob_name)}"
    blob.download_to_filename(temp_file)

    download_virus_definitions()
    code, output = scan_file(temp_file)
    if code == 0:
        dest_bucket = storage_client.bucket(DEST_BUCKET)
        dest_blob = dest_bucket.blob(blob_name)
        dest_blob.upload_from_filename(temp_file)
        print(f"{blob_name} is clean, moved to {DEST_BUCKET}.")
    else:
        quarantine_bucket = storage_client.bucket(QUARANTINE_BUCKET)
        quarantine_blob = quarantine_bucket.blob(blob_name)
        quarantine_blob.upload_from_filename(temp_file)
        quarantine_path = f"gs://{QUARANTINE_BUCKET}/{blob_name}"
        send_slack_alert(blob_name, output, quarantine_path)
        print(f"{blob_name} is infected! Moved to quarantine and notified Slack.")

    blob.delete()
    os.remove(temp_file)

@app.route("/", methods=["POST"])
def main_entrypoint():
    envelope = request.get_json(silent=True)
    if not envelope or "message" not in envelope:
        return ("Bad Request: No Pub/Sub message received", 400)

    pubsub_message = envelope["message"]
    if isinstance(pubsub_message, dict) and "data" in pubsub_message:
        try:
            event = json.loads(base64.b64decode(pubsub_message["data"]).decode("utf-8"))
            process_file(event)
        except Exception as e:
            print(f"Error processing event: {e}")
            return ("Bad Request: Event decoding failed", 400)
    else:
        print("No data in Pub/Sub message")
        return ("Bad Request: No data in message", 400)

    return ("", 204)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
