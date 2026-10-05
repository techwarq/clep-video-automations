#!/usr/bin/env bash
# One-time: create the Spot render VM. After this the API starts it on demand and it powers itself off when idle.
# Needs (created once, see README): image in Artifact Registry, service account video-worker, secret video-worker-env.
set -euo pipefail
P=${GCP_PROJECT:-doctosheet-be}; ZONE=${GCP_ZONE:-us-east4-a}; VM=${GCP_VM:-video-worker}
IMAGE=us-east4-docker.pkg.dev/$P/video-automation/engine:latest

gcloud compute instances create "$VM" --project "$P" --zone "$ZONE" \
  --machine-type e2-standard-4 \
  --provisioning-model SPOT --instance-termination-action STOP \
  --image-family debian-12 --image-project debian-cloud --boot-disk-size 30GB --boot-disk-type pd-balanced \
  --service-account "video-worker@$P.iam.gserviceaccount.com" --scopes cloud-platform \
  --metadata-from-file startup-script="$(dirname "$0")/startup.sh" \
  --metadata image="$IMAGE",env-secret=video-worker-env,idle-minutes=10

# the API's service account may see and start this VM, nothing else
gcloud compute instances add-iam-policy-binding "$VM" --project "$P" --zone "$ZONE" \
  --member "serviceAccount:video-dispatcher@$P.iam.gserviceaccount.com" --role roles/compute.instanceAdmin.v1
