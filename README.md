# GCP Cloud Function: File Scanner with ClamAV and Slack Alerts

This repository provides a **Google Cloud Run Function** to automatically scan files uploaded by clients to a Google Cloud Storage (GCS) bucket.

- **If the file is clean:** it is moved to the main client files bucket.
- **If malware is detected:** it is moved to a quarantined files bucket, and a Slack alert is sent.

---

## Features

- **[Google Cloud Storage (GCS)](https://cloud.google.com/storage?hl=en):** Scanning, quarantined and clean buckets for clients files.
- **[Cloud Pub/Sub](https://cloud.google.com/pubsub/docs):** event-driven notifications to scans files on upload to a "scanning" GCS bucket.
- **[ClamAV](https://www.clamav.net/):** Malware detection antivirus.
- **[Cloud Run](https://cloud.google.com/run?hl=en):** containerized cloud functions with ClamAV
- **[Slack notifications](https://api.slack.com/messaging/webhooks):** Alerts a specified channel if malware is found with Slack Incoming Webhooks.

---

## Architecture

```text
[Clients] 
   |
   v
[GCS Scanning Bucket] --> (new upload event via Pub/Sub) --> [Cloud Run Function (ClamAV scan)]
                                                                  |
                                          ------------------------+------------------------
                                         |                                                 |
                                         v                                                 v
                                     [If clean]                                      [If infected]
                                  Move file to clean                      Move file to quarantine bucket
                                 clients files bucket                          + send Slack alert

```

### File Structure
```text
bucket-scanning
├── Dockerfile
├── main.py
└── requirements.txt

	•	Dockerfile: Installs Python, ClamAV, and your dependencies.
	•	main.py: Cloud Function handler (scan, move/delete, notify).
	•	requirements.txt: Python dependencies.
```

---

## Usage

1. Set Up Buckets
    - file-scanning-bucket: where clients upload files.
    - clients-files-bucket: receives clean, scanned files.

2. Create a Slack Incoming Webhook, See: https://api.slack.com/messaging/webhooks

3. Clone This Repo
    ```sh
    git clone ghttps://github.com/niv-devops/bucket-scannig.git
    cd cloud-functions/bucket-scanning
    ```

4. Connect to gcloud cli & auth with docker (`gcloud auth configure-docker`)

5. Build and Deploy to Cloud Run
    ```sh
    # Build Docker image for the function
    gcloud auth configure-docker
    gcloud builds submit --tag gcr.io/[PROJECT_ID]/file-scanner

    # Create the cloud function with Cloud Run
    gcloud run deploy file-scanner \
    --image=gcr.io/<PROJECT_ID>/file-scanner \
    --region=<bucket_region> \
    --memory=2Gi \
    --timeout=300 \
    --no-allow-unauthenticated \
    --set-env-vars="DEST_BUCKET=<clients_clean_files>,QUARANTINE_BUCKET=<client_infected_files>,SLACK_WEBHOOK=https://hooks.slack.com/services/XXX/XXX/XXX"
    ```

6. Set Up GCS to Pub/Sub Notification

    `gsutil notification create -t gcs-file-uploads -f json gs://<Scanning_bucket>`

7. Create a Pub/Sub Push Subscription to Cloud Run

    ```sh
    gcloud pubsub subscriptions create file-scanner-sub \
    --topic=gcs-file-uploads \
    --push-endpoint=gcloud pubsub subscriptions create file-scanner-sub \
    --topic=gcs-file-uploads \
    --push-endpoint=https://file-scanner-XXXXX.a.run.app/ \
    --push-auth-service-account=YOUR-SERVICE-ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com
    ```
	•	Replace with your actual Cloud Run URL and a service account with roles/run.invoker on your Cloud Run service.

---

## Permissions

| Component                              | IAM Role                        | Assignee/Who Needs It                                 | Purpose                                  |
|-----------------------------------------|----------------------------------|-------------------------------------------------------|-------------------------------------------|
| GCS Service Account                     | roles/pubsub.publisher           | `service-[PROJECT_NUMBER]@gs-project-accounts.iam.gserviceaccount.com` | Allow GCS to publish events to Pub/Sub    |
| User configuring notifications/subs     | roles/storage.admin <br>roles/pubsub.editor | Your admin or setup user                               | Allow creating GCS notifications and Pub/Sub subscriptions |
| Cloud Run Push Subscription Service Account | roles/run.invoker                 | Service account used by Pub/Sub push                  | Allow Pub/Sub to invoke Cloud Run service |
| Cloud Run Service Account               | roles/storage.objectViewer <br>roles/storage.objectAdmin | Service account Cloud Run runs as                      | Read/write/delete files in both buckets   |

### Grant Pub/Sub Publisher role:

Get your project number with
`gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)'`

Then execute:

```sh
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:service-YOUR_PROJECT_NUMBER@gs-project-accounts.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```

---

## Logs and Troubleshooting
- Cloud Run logs: Cloud Run > Your Service > Logs
- Pub/Sub: View topics, subscriptions, and messages in Cloud Pub/Sub.
- IAM: Make sure all permissions are set (see above).
