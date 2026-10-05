#!/usr/bin/env bash
# GCE startup script (runs as root on every boot of the video-worker VM).
#   boot → pull the latest image → run the worker → it exits after IDLE_EXIT_MINUTES with an empty queue → power off.
# The API starts the VM again when a job arrives. Settings come from instance metadata (set in deploy/create-vm.sh).
set -uo pipefail
md() { curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
IMAGE=$(md image); SECRET=$(md env-secret); IDLE=$(md idle-minutes || echo 10)

command -v docker >/dev/null || { apt-get update -q && apt-get install -yq docker.io; }
gcloud auth configure-docker "${IMAGE%%/*}" --quiet
gcloud secrets versions access latest --secret "$SECRET" > /run/worker.env      # tmpfs: never written to disk
docker pull "$IMAGE" || echo "pull failed, using the cached image"
docker image prune -f >/dev/null

while true; do
  docker run --rm --name video-worker --env-file /run/worker.env -e IDLE_EXIT_MINUTES="$IDLE" --shm-size 1g "$IMAGE"
  code=$?
  if [ "$code" -eq 0 ]; then
    echo "worker idle: powering off"; shutdown -h now; exit 0
  fi
  echo "worker exited $code: restarting in 10s"; sleep 10
done
