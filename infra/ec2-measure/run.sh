#!/usr/bin/env bash
set -Eeuo pipefail

region="${AWS_REGION:-us-east-1}"
profile="${AWS_PROFILE:-vps-setup-e2e}"
repo_root="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
infra_dir="$repo_root/infra/ec2-measure"
report_dir="${REPORT_DIR:-$repo_root/.ec2-measure-report}"
ssh_user="${EC2_SSH_USER:-ubuntu}"
run_id="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$(openssl rand -hex 4)}"
instance_type="${INSTANCE_TYPE:-}"
use_spot="${EC2_USE_SPOT:-true}"
instance_id=""
public_ip=""
compose_env=""
terraform_cmd=()
instance_started_at=""
launched_instance_type=""
launched_az=""
instance_lifecycle=""
instance_launch_time=""
hourly_price=""
price_source=""
apply_started=false

mkdir -p "$report_dir"
exec > >(tee -a "$report_dir/run-$run_id.log") 2>&1

die() {
  echo "ERROR: $*" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

for command_name in aws terraform curl jq ssh scp openssl; do
  need_command "$command_name"
done

aws_cli=(aws --profile "$profile" --region "$region")
[[ "$profile" == "vps-setup-e2e" ]] || die "AWS_PROFILE must be vps-setup-e2e"
if ! identity="$("${aws_cli[@]}" sts get-caller-identity --query Account --output text 2>&1)"; then
  echo "$identity" >&2
  echo "AWS profile $profile is unavailable. Captain must run: aws configure --profile $profile" >&2
  exit 1
fi
echo "aws_account=$identity profile=$profile region=$region"

[[ -n "${EC2_KEY_NAME:-}" ]] || die "set EC2_KEY_NAME to an existing EC2 key pair"
[[ -n "${EC2_SSH_PRIVATE_KEY:-}" ]] || die "set EC2_SSH_PRIVATE_KEY to the matching private key path"
[[ -r "$EC2_SSH_PRIVATE_KEY" ]] || die "cannot read EC2_SSH_PRIVATE_KEY=$EC2_SSH_PRIVATE_KEY"
[[ -n "${API_IMAGE:-}" ]] || die "set API_IMAGE to a GHCR digest reference"
[[ -n "${WEB_IMAGE:-}" ]] || die "set WEB_IMAGE to a GHCR digest reference"
[[ "$API_IMAGE" == *@sha256:* ]] || die "API_IMAGE must contain @sha256:<digest>"
[[ "$WEB_IMAGE" == *@sha256:* ]] || die "WEB_IMAGE must contain @sha256:<digest>"
[[ -n "${TUNNEL_TOKEN:-}" ]] || die "set TUNNEL_TOKEN to start cloudflared"
if [[ -z "${GHCR_USERNAME:-}" || -z "${GHCR_TOKEN:-}" ]]; then
  die "set GHCR_USERNAME and GHCR_TOKEN for the private GHCR images"
fi

terraform_cmd=(terraform -chdir="$infra_dir")

list_resources() {
  local instances volumes groups addresses
  instances="$("${aws_cli[@]}" ec2 describe-instances --filters "Name=tag:RunId,Values=$run_id" "Name=instance-state-name,Values=pending,running,stopping,stopped,shutting-down" --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name}' --output json)"
  volumes="$("${aws_cli[@]}" ec2 describe-volumes --filters "Name=tag:RunId,Values=$run_id" --query 'Volumes[].{Id:VolumeId,State:State}' --output json)"
  groups="$("${aws_cli[@]}" ec2 describe-security-groups --filters "Name=tag:RunId,Values=$run_id" --query 'SecurityGroups[].{Id:GroupId,Name:GroupName}' --output json)"
  addresses="$("${aws_cli[@]}" ec2 describe-addresses --filters "Name=tag:RunId,Values=$run_id" --query 'Addresses[].{Id:AllocationId,PublicIp:PublicIp}' --output json)"
  printf '%s\n' "post_destroy_instances=$instances" "post_destroy_volumes=$volumes" "post_destroy_security_groups=$groups" "post_destroy_addresses=$addresses" | tee "$report_dir/post-destroy-$run_id.txt"
  [[ "$instances" == "[]" && "$volumes" == "[]" && "$groups" == "[]" && "$addresses" == "[]" ]] || {
    echo "ERROR: tagged AWS resources remain after destroy" >&2
    return 1
  }
}

cleanup() {
  local status=$?
  local destroy_succeeded=false
  local instance_ended_at
  trap - EXIT INT TERM
  if [[ -n "$public_ip" && -n "$instance_id" ]]; then
    scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i "$EC2_SSH_PRIVATE_KEY" "$ssh_user@$public_ip:/var/log/tsdhn-ec2-measure.log" "$report_dir/cloud-init-$run_id.log" 2>/dev/null || true
    scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i "$EC2_SSH_PRIVATE_KEY" "$ssh_user@$public_ip:/var/log/cloud-init-output.log" "$report_dir/cloud-init-output-$run_id.log" 2>/dev/null || true
  fi
  if [[ "$apply_started" == true ]]; then
    echo "Destroying Terraform resources for $run_id"
    if "${terraform_cmd[@]}" destroy -auto-approve -input=false -no-color; then
      destroy_succeeded=true
    else
      status=1
      echo "Terraform destroy failed; state was retained. Retry with: terraform -chdir=$infra_dir destroy -auto-approve -input=false -no-color" >&2
    fi
  fi
  instance_ended_at="$(date -u +%s.%N)"
  if [[ -n "$hourly_price" && -n "$instance_started_at" ]]; then
    instance_elapsed_hours="$(awk -v start="$instance_started_at" -v end="$instance_ended_at" 'BEGIN {printf "%.6f", (end-start)/3600}')"
    estimated_cost="$(awk -v h="$instance_elapsed_hours" -v p="$hourly_price" 'BEGIN {printf "%.6f", h*p}')"
    printf '%s\n' "instance_elapsed_hours=$instance_elapsed_hours" "launched_instance_type=$launched_instance_type" "launched_availability_zone=$launched_az" "instance_lifecycle=$instance_lifecycle" "hourly_price_usd=$hourly_price" "price_source=$price_source" "estimated_instance_cost_usd=$estimated_cost" | tee "$report_dir/cost-$run_id.txt"
  fi
  if [[ "$apply_started" == true ]]; then
    list_resources || status=1
  fi
  if [[ -n "$compose_env" ]]; then
    rm -f "$compose_env"
  fi
  if [[ "$destroy_succeeded" == true ]]; then
    find "$infra_dir" -maxdepth 1 -type f -name 'terraform.tfstate*' -delete
    if [[ -d "$infra_dir/.terraform" ]]; then
      find "$infra_dir/.terraform" -mindepth 1 -delete
      rmdir "$infra_dir/.terraform"
    fi
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

runner_cidr="${RUNNER_IPV4_CIDR:-}"
if [[ -z "$runner_cidr" ]]; then
  runner_ip="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
  [[ "$runner_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || die "invalid runner IP: $runner_ip"
  runner_cidr="$runner_ip/32"
fi

compose_env="$report_dir/prod-$run_id.env"
umask 077
secret() { openssl rand -hex 32; }
write_env_value() { printf '%s=%q\n' "$1" "$2"; }
compute_api_token="$(secret)"
{
  write_env_value COMPUTE_API_TOKEN "$compute_api_token"
  write_env_value BETTER_AUTH_SECRET "$(secret)"
  write_env_value ORIGIN "http://127.0.0.1:3000"
  write_env_value APP_DB_PASSWORD "$(secret)"
  write_env_value COMPUTE_PRODUCER_PASSWORD "$(secret)"
  write_env_value COMPUTE_WORKER_PASSWORD "$(secret)"
  write_env_value COMPUTE_PURGER_PASSWORD "$(secret)"
  write_env_value TSDHN_S3_ACCESS_KEY "$(openssl rand -hex 10)"
  write_env_value TSDHN_S3_SECRET_KEY "$(openssl rand -hex 20)"
  write_env_value TSDHN_S3_BUCKET "tsdhn-results"
  write_env_value COMPUTE_QUEUE "simulations"
  write_env_value COMPUTE_QUEUE_SCHEMA "task_queue"
  write_env_value POSTGRES_PASSWORD "$(secret)"
  write_env_value API_IMAGE "$API_IMAGE"
  write_env_value WEB_IMAGE "$WEB_IMAGE"
  write_env_value TUNNEL_TOKEN "$TUNNEL_TOKEN"
  write_env_value TSDHN_WEB_PORT "3000"
  write_env_value GHCR_USERNAME "$GHCR_USERNAME"
  write_env_value GHCR_TOKEN "$GHCR_TOKEN"
} > "$compose_env"
chmod 600 "$compose_env"

vpc_id="$("${aws_cli[@]}" ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)"
subnets_file="$report_dir/subnets-$run_id.json"
"${aws_cli[@]}" ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc_id" \
  --query 'sort_by(Subnets, &AvailabilityZone)[].{SubnetId:SubnetId,AvailabilityZone:AvailabilityZone}' \
  --output json > "$subnets_file"
subnet_id="$(jq -r '.[0].SubnetId // empty' "$subnets_file")"
[[ -n "$subnet_id" && "$subnet_id" != None ]] || die "the default VPC has no subnet"
availability_zone="$(jq -r '.[0].AvailabilityZone // empty' "$subnets_file")"
[[ -n "$availability_zone" && "$availability_zone" != None ]] || die "could not determine the launch availability zone"
mapfile -t subnet_records < <(jq -r '.[] | [.AvailabilityZone, .SubnetId] | @tsv' "$subnets_file")

manual_instance_type=false
if [[ -z "$instance_type" ]]; then
  instance_types_file="$report_dir/instance-types-$run_id.json"
  "${aws_cli[@]}" ec2 describe-instance-types \
    --filters \
      Name=vcpu-info.default-vcpus,Values=4 \
      Name=memory-info.size-in-mib,Values=8192 \
      Name=current-generation,Values=true \
      Name=processor-info.supported-architecture,Values=x86_64 \
    --query 'InstanceTypes' --output json > "$instance_types_file"
  mapfile -t candidates < <(jq -r '.[].InstanceType' "$instance_types_file" | sort)
  ((${#candidates[@]} > 0)) || die "no current x86_64 4-vCPU 8-GiB instance type is available"
else
  manual_instance_type=true
  candidates=("$instance_type")
fi
candidate_types_json="$(printf '%s\n' "${candidates[@]}" | jq -R -s 'split("\n") | map(select(length > 0))')"

offered_types_file="$report_dir/offered-types-$run_id.tsv"
: > "$offered_types_file"
for subnet_record in "${subnet_records[@]}"; do
  IFS=$'\t' read -r candidate_az candidate_subnet_id <<< "$subnet_record"
  offerings_file="$report_dir/offerings-$run_id-$candidate_az.json"
  "${aws_cli[@]}" ec2 describe-instance-type-offerings \
    --location-type availability-zone \
    --filters "Name=location,Values=$candidate_az" \
    --query 'InstanceTypeOfferings[].InstanceType' --output json > "$offerings_file"
  while IFS= read -r offered_type; do
    printf '%s\t%s\t%s\n' "$candidate_az" "$candidate_subnet_id" "$offered_type" >> "$offered_types_file"
  done < <(jq -r --argjson candidates "$candidate_types_json" '.[] | select(. as $type | $candidates | index($type))' "$offerings_file")
done
[[ -s "$offered_types_file" ]] || die "no qualifying instance type is offered in any default-VPC availability zone"

pricing_url=https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.json
pricing_file="$report_dir/ec2-pricing-candidates-$run_id.json"
curl -fsS "$pricing_url" -o "$pricing_file"
on_demand_prices_file="$report_dir/on-demand-prices-$run_id.tsv"
jq -r --argjson candidates "$candidate_types_json" '
  [ .products[]
    | select(.productFamily == "Compute Instance")
    | .attributes.instanceType as $type
    | select($candidates | index($type))
    | select(.attributes.operatingSystem == "Linux" and .attributes.tenancy == "Shared" and .attributes.capacitystatus == "Used" and .attributes.preInstalledSw == "NA")
    | .terms.OnDemand[]
    | .priceDimensions[]
    | select(.unit == "Hrs")
    | {type: $type, price: (.pricePerUnit.USD | tonumber)}
  ]
  | group_by(.type)
  | map({type: .[0].type, price: (map(.price) | min)})
  | .[]
  | [.type, (.price | tostring)]
  | @tsv
' "$pricing_file" > "$on_demand_prices_file"

spot_prices_file="$report_dir/spot-prices-$run_id.json"
spot_price=""
spot_files=()
if [[ "$use_spot" == true ]]; then
  start_time="$(date -u -d '2 hours ago' +%Y-%m-%dT%H:%M:%SZ)"
  while IFS= read -r candidate_az; do
    mapfile -t az_candidates < <(awk -F '\t' -v az="$candidate_az" '$1 == az {print $3}' "$offered_types_file" | sort -u)
    ((${#az_candidates[@]} > 0)) || continue
    az_spot_file="$report_dir/spot-prices-$run_id-$candidate_az.json"
    "${aws_cli[@]}" ec2 describe-spot-price-history \
      --instance-types "${az_candidates[@]}" \
      --availability-zone "$candidate_az" \
      --product-descriptions 'Linux/UNIX' --start-time "$start_time" \
      --query 'SpotPriceHistory' --output json > "$az_spot_file"
    az_spot_with_az_file="$report_dir/spot-prices-$run_id-$candidate_az-with-az.json"
    jq --arg az "$candidate_az" 'map(. + {AvailabilityZone: $az})' "$az_spot_file" > "$az_spot_with_az_file"
    spot_files+=("$az_spot_with_az_file")
  done < <(cut -f1 "$offered_types_file" | sort -u)
  if ((${#spot_files[@]} > 0)); then
    jq -s 'add' "${spot_files[@]}" > "$spot_prices_file"
    spot_selection="$(jq -c '
      group_by([.AvailabilityZone, .InstanceType])
      | map(max_by(.Timestamp) | {AvailabilityZone, InstanceType, SpotPrice})
      | sort_by(.SpotPrice | tonumber)
      | .[0] // empty
    ' "$spot_prices_file")"
    if [[ -n "$spot_selection" ]]; then
      availability_zone="$(jq -r '.AvailabilityZone' <<< "$spot_selection")"
      instance_type="$(jq -r '.InstanceType' <<< "$spot_selection")"
      spot_price="$(jq -r '.SpotPrice' <<< "$spot_selection")"
      subnet_id="$(jq -r --arg az "$availability_zone" '[.[] | select(.AvailabilityZone == $az) | .SubnetId] | .[0] // empty' "$subnets_file")"
    else
      echo "No spot price history is available in an offered AZ; falling back to on-demand"
      use_spot=false
    fi
  else
    echo "No spot price history is available in an offered AZ; falling back to on-demand"
    use_spot=false
  fi
else
  printf '%s\n' '[]' > "$spot_prices_file"
fi

if [[ "$use_spot" != true ]]; then
  if [[ "$manual_instance_type" == true ]]; then
    availability_zone="$(awk -F '\t' 'NR == 1 {print $1}' "$offered_types_file")"
    subnet_id="$(awk -F '\t' 'NR == 1 {print $2}' "$offered_types_file")"
  else
    on_demand_choice="$(awk -F '\t' 'NR == FNR {price[$1] = $2; next} $3 in price {print price[$3] "\t" $1 "\t" $2 "\t" $3}' "$on_demand_prices_file" "$offered_types_file" | sort -n -k1,1 | head -n 1)"
    [[ -n "$on_demand_choice" ]] || die "no on-demand price is available for a qualifying offered instance type"
    IFS=$'\t' read -r _on_demand_price availability_zone subnet_id instance_type <<< "$on_demand_choice"
  fi
fi
[[ -n "$subnet_id" && "$subnet_id" != None ]] || die "could not determine the subnet for $availability_zone"
echo "run_id=$run_id instance_type=$instance_type availability_zone=$availability_zone spot_price=${spot_price:-unavailable} runner_cidr=$runner_cidr"

export AWS_PROFILE="$profile"
export AWS_REGION="$region"
export TF_VAR_region="$region"
export TF_VAR_run_id="$run_id"
export TF_VAR_instance_type="$instance_type"
export TF_VAR_use_spot="$use_spot"
export TF_VAR_key_name="$EC2_KEY_NAME"
export TF_VAR_runner_cidr="$runner_cidr"
export TF_VAR_subnet_id="$subnet_id"

"${terraform_cmd[@]}" init -input=false -no-color
apply_started=true
if ! "${terraform_cmd[@]}" apply -auto-approve -input=false -no-color; then
  if [[ "$use_spot" == true ]]; then
    echo "Spot launch failed; retrying the same instance type on demand"
    use_spot=false
    export TF_VAR_use_spot=false
    "${terraform_cmd[@]}" apply -auto-approve -input=false -no-color
  else
    exit 1
  fi
fi

instance_id="$("${terraform_cmd[@]}" output -raw instance_id)"
public_ip="$("${terraform_cmd[@]}" output -raw public_ip)"
instance_info_file="$report_dir/instance-$run_id.json"
"${aws_cli[@]}" ec2 describe-instances --instance-ids "$instance_id" \
  --query 'Reservations[0].Instances[0]' --output json > "$instance_info_file"
launched_instance_type="$(jq -r '.InstanceType' "$instance_info_file")"
launched_az="$(jq -r '.Placement.AvailabilityZone' "$instance_info_file")"
instance_lifecycle="$(jq -r '.InstanceLifecycle // "on-demand"' "$instance_info_file")"
instance_launch_time="$(jq -r '.LaunchTime' "$instance_info_file")"
instance_started_at="$(date -u -d "$instance_launch_time" +%s.%N)"
echo "instance_id=$instance_id public_ip=$public_ip"
ssh_opts=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -i "$EC2_SSH_PRIVATE_KEY")
for _ in $(seq 1 120); do
  if ssh "${ssh_opts[@]}" "$ssh_user@$public_ip" true 2>/dev/null; then
    break
  fi
  sleep 5
done
ssh "${ssh_opts[@]}" "$ssh_user@$public_ip" true
scp -q "${ssh_opts[@]}" "$compose_env" "$ssh_user@$public_ip:/tmp/tsdhn-prod.env"
ssh "${ssh_opts[@]}" "$ssh_user@$public_ip" sudo install -o root -g root -m 600 /tmp/tsdhn-prod.env /opt/tsdhn/prod.env
ssh "${ssh_opts[@]}" "$ssh_user@$public_ip" rm -f /tmp/tsdhn-prod.env

bootstrap_timeout_seconds=1800
bootstrap_started_at="$(date -u +%s)"
bootstrap_ready=false
while (( $(date -u +%s) - bootstrap_started_at < bootstrap_timeout_seconds )); do
  cloud_init_status="$(ssh "${ssh_opts[@]}" "$ssh_user@$public_ip" sudo cloud-init status --format json 2>/dev/null || true)"
  cloud_init_state="$(jq -r '.status // empty' <<<"$cloud_init_status" 2>/dev/null || true)"
  if [[ "$cloud_init_state" == error ]]; then
    ssh "${ssh_opts[@]}" "$ssh_user@$public_ip" sudo cloud-init status --long || true
    ssh "${ssh_opts[@]}" "$ssh_user@$public_ip" sudo tail -n 100 /var/log/cloud-init-output.log || true
    die "cloud-init reported an error"
  fi
  if ssh "${ssh_opts[@]}" "$ssh_user@$public_ip" test -f /var/lib/tsdhn-ec2-measure.ready; then
    bootstrap_ready=true
    break
  fi
  sleep 5
done
[[ "$bootstrap_ready" == true ]] || die "bootstrap did not become ready within ${bootstrap_timeout_seconds}s"

measure_file="$report_dir/measurement-$run_id.json"
ssh "${ssh_opts[@]}" "$ssh_user@$public_ip" env COMPUTE_API_TOKEN="$compute_api_token" bash -s > "$measure_file" <<'REMOTE_MEASURE'
set -Eeuo pipefail
cd /opt/tsdhn
set -a
source /opt/tsdhn/prod.env
set +a
compose=(docker compose -f /opt/tsdhn/compose.prod.yml)
api() { "${compose[@]}" exec -T -e MEASURE_API_TOKEN="$COMPUTE_API_TOKEN" api sh -c 'curl -fsS -H "Authorization: Bearer $MEASURE_API_TOKEN" "$@"' sh "$@"; }
simulation_id="$(cat /proc/sys/kernel/random/uuid)"
payload="$(jq -cn --arg id "$simulation_id" '{simulation_id:$id,input:{Mw:8.0,h:10.0,lat0:-20.5,lon0:-70.5,hhmm:"0000",dia:"23"}}')"
worker_id="$("${compose[@]}" ps -q worker)"
read_cgroup_bytes() {
  local metric="$1" path="/sys/fs/cgroup/$1" value
  if ! value="$(docker exec "$worker_id" cat "$path" 2>/dev/null)"; then
    echo "ERROR: worker cgroup metric is missing: $path" >&2
    exit 1
  fi
  [[ "$value" =~ ^[0-9]+$ ]] || { echo "ERROR: worker cgroup metric is not an integer: $path" >&2; exit 1; }
  printf '%s\n' "$value"
}

cpu_start="$(docker exec "$worker_id" awk '$1 == "usage_usec" {print $2}' /sys/fs/cgroup/cpu.stat)"
worker_cgroup_idle_bytes="$(read_cgroup_bytes memory.current)"
disk_start="$(df -B1 --output=used / | tail -n 1 | tr -d '[:space:]')"
queued_at="$(date -u +%s.%N)"
created="$(api -X POST -H 'Content-Type: application/json' -d "$payload" http://127.0.0.1:8000/api/v1/jobs)"
echo "$created" >&2
status=queued
while [[ "$status" != completed && "$status" != failed ]]; do
  sleep 5
  current="$(api http://127.0.0.1:8000/api/v1/jobs/$simulation_id)"
  status="$(jq -r .status <<<"$current")"
done
finished_at="$(date -u +%s.%N)"
[[ "$status" == completed ]] || { echo "$current" >&2; exit 1; }
cpu_end="$(docker exec "$worker_id" awk '$1 == "usage_usec" {print $2}' /sys/fs/cgroup/cpu.stat)"
worker_cgroup_peak_bytes="$(read_cgroup_bytes memory.peak)"
disk_end="$(df -B1 --output=used / | tail -n 1 | tr -d '[:space:]')"
outputs="$(api http://127.0.0.1:8000/api/v1/jobs/$simulation_id/outputs)"
output_sizes='[]'
while IFS=$'\t' read -r name; do
  [[ -n "$name" ]] || continue
  location="$(api -o /dev/null -w '%{redirect_url}' http://127.0.0.1:8000/api/v1/jobs/$simulation_id/outputs/$name)"
  bytes="$("${compose[@]}" exec -T api sh -c 'curl -fsSL "$1" -o /tmp/measure-output && stat -c %s /tmp/measure-output' sh "$location")"
  output_sizes="$(jq -c --arg name "$name" --argjson bytes "$bytes" '. + [{name:$name,bytes:$bytes}]' <<<"$output_sizes")"
done < <(jq -r '.outputs[].name' <<<"$outputs")
cpu_seconds="$(awk -v a="$cpu_start" -v b="$cpu_end" 'BEGIN {printf "%.6f", (b-a)/1000000}')"
queue_to_complete_seconds="$(awk -v a="$queued_at" -v b="$finished_at" 'BEGIN {printf "%.3f", b-a}')"
jq -n --arg simulation_id "$simulation_id" --arg status "$status" --arg q "$queue_to_complete_seconds" --arg cpu "$cpu_seconds" --arg idle "$worker_cgroup_idle_bytes" --arg peak "$worker_cgroup_peak_bytes" --arg ds "$disk_start" --arg de "$disk_end" --argjson output_sizes "$output_sizes" --argjson final_status "$current" '{simulation_id,status,queue_to_complete_seconds:($q|tonumber),cpu_seconds:($cpu|tonumber),worker_cgroup_peak_bytes:($peak|tonumber),worker_cgroup_idle_bytes:($idle|tonumber),disk_used_start_bytes:($ds|tonumber),disk_used_end_bytes:($de|tonumber),output_sizes,final_status}'
REMOTE_MEASURE
cat "$measure_file"

if [[ "$instance_lifecycle" == spot ]]; then
  launch_history_file="$report_dir/spot-launch-price-$run_id.json"
  history_start="$(date -u -d "$instance_launch_time - 10 minutes" +%Y-%m-%dT%H:%M:%SZ)"
  history_end="$(date -u -d "$instance_launch_time + 10 minutes" +%Y-%m-%dT%H:%M:%SZ)"
  "${aws_cli[@]}" ec2 describe-spot-price-history \
    --instance-types "$launched_instance_type" --availability-zone "$launched_az" \
    --product-descriptions 'Linux/UNIX' --start-time "$history_start" \
    --end-time "$history_end" --query 'SpotPriceHistory' --output json > "$launch_history_file"
  hourly_price="$(jq -r --arg launch "$instance_launch_time" '
    ([ .[] | select(.Timestamp <= $launch) ] | sort_by(.Timestamp) | .[-1].SpotPrice)
    // ([ .[] ] | sort_by(.Timestamp) | .[0].SpotPrice)
    // empty
  ' "$launch_history_file")"
  price_source="AWS EC2 DescribeSpotPriceHistory for $launched_az at $instance_launch_time"
fi
if [[ -z "$hourly_price" ]]; then
  price_source="AWS EC2 public pricing API candidate data for $launched_instance_type"
  hourly_price="$(awk -F '\t' -v type="$launched_instance_type" '$1 == type {print $2; exit}' "$on_demand_prices_file")"
fi
[[ -n "$hourly_price" ]] || die "could not determine hourly price for $launched_instance_type"
