#!/usr/bin/env bash

set -e

variant=${1:-${VARIANT}}
deployment=${2:-${DEPLOYMENT_NAME}}
namespace=${3:-${NAMESPACE}}

[[ -z $namespace ]] && namespace="default"

path=$(dirname "$0")

timed() {
  end=$(date +%s)
  dt=$(($end - $1))
  dd=$(($dt / 86400))
  dt2=$(($dt - 86400 * $dd))
  dh=$(($dt2 / 3600))
  dt3=$(($dt2 - 3600 * $dh))
  dm=$(($dt3 / 60))
  ds=$(($dt3 - 60 * $dm))

  LC_NUMERIC=C printf "\nTotal runtime: %02d min %02d seconds\n" "$dm" "$ds"
}

success() {
  newman run \
    --delay-request=100 \
    --folder=success \
    --export-environment "$variant"/postman/environment.json \
    --environment "$variant"/postman/environment.json \
    "$variant"/postman/collection.json
}

step() {
  local step=$1
  local replicas
  [[ $((step % 2)) -eq 0 ]] && replicas=1 || replicas=0

  echo "=== Step ${step_number}: scale ${deployment} to ${replicas} ==="
  echo "DEBUG: deployment='${deployment}'"
  echo "DEBUG: namespace='${namespace}'"
  echo "DEBUG: replicas='${replicas}'"

  kubectl scale deployment "$deployment" -n "$namespace" --replicas "$replicas" 
  
  kubectl rollout status deployment/"$deployment" -n "$namespace" --timeout=120s

  if [[ "$replicas" -eq 1 ]]; then
    kubectl rollout status deployment/"$deployment" \
      -n "$namespace" --timeout=120s

    # Ждём появления готового endpoint
    echo "=== Waiting for $deployment endpoint ==="
    for i in $(seq 1 30); do
      ENDPOINTS=$(kubectl get endpoints "$deployment" \
        -n "$namespace" \
        -o jsonpath='{.subsets[*].addresses[*].ip}')

      if [[ -n "$ENDPOINTS" ]]; then
        echo "Endpoint is ready: $ENDPOINTS"
        break
      fi

      echo "Waiting for endpoint... ($i/30)"
      sleep 2
    done

    if [[ -z "$ENDPOINTS" ]]; then
      echo "ERROR: $deployment endpoint did not become ready"
      kubectl get pods -n "$namespace" -o wide
      kubectl describe deployment "$deployment" -n "$namespace"
      exit 1
    fi

    # Даём приложению время начать обрабатывать запросы
    sleep 5
  fi

  newman run \
    --delay-request=100 \
    --folder=step"$step" \
    --export-environment "$variant"/postman/environment.json \
    --environment "$variant"/postman/environment.json \
    "$variant"/postman/collection.json

  printf "=== Step %d completed ===\n" "$step"
}

start=$(date +%s)
trap 'timed $start' EXIT

printf "=== Start test scenario ===\n"

# success execute
success

# stop service
step 1

# start service
step 2

# stop service
step 3

# start service
step 4