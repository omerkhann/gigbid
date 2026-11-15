"""Launch an Oracle Cloud Always Free ARM VM (VM.Standard.A1.Flex) for GigBid, retrying until capacity opens.

  uv run --with oci python infra/deploy/oci_retry.py                      # from a laptop, until it succeeds
  python infra/deploy/oci_retry.py --rounds 10 --user-data first_boot.sh  # from GitHub Actions (oci-launch.yml)

Stays inside the Always Free limits (A1: 4 OCPUs and 24 GB in total; boot volume 50 GB of the 200 GB).
Each round tries one shape (smallest first: most often available; Oracle answers 429 to bursts) in every
availability domain. "Out of host capacity", 429s and network errors just wait for the next round.

Idempotent: if an instance named "gigbid" already exists (not terminated), it prints its address and
exits 0 without launching, so a scheduled job can run this every few minutes safely.
--user-data: a shell script the VM runs once on first boot (cloud-init), e.g. one that runs setup_vm.sh.

Needs: ~/.oci/config (Console > My profile > API keys), a VCN with a public subnet (Start VCN Wizard >
"VCN with Internet Connectivity"), and an SSH public key (--ssh-key, or the SSH_PUBLIC_KEY variable).
Exit codes: 0 launched or already exists; 3 no capacity within --rounds.
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time
from pathlib import Path

import oci

NAME = "gigbid"
SHAPE = "VM.Standard.A1.Flex"
SHAPES = [(1, 6), (2, 12), (4, 24)]          # (OCPUs, GB), smallest first: most often available
RETRYABLE = ("out of host capacity", "out of capacity", "toomanyrequests", "internalerror")
ALIVE = {"PROVISIONING", "STARTING", "RUNNING", "STOPPING", "STOPPED"}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def summary(text: str) -> None:
    """Also write to the GitHub Actions job summary, when running there."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def pick_image(compute, compartment: str) -> str:
    images = compute.list_images(compartment, operating_system="Canonical Ubuntu", operating_system_version="24.04",
                                 shape=SHAPE, sort_by="TIMECREATED", sort_order="DESC").data
    if not images:
        sys.exit("No Ubuntu 24.04 aarch64 image found for A1 in this region")
    log(f"image: {images[0].display_name}")
    return images[0].id


def pick_subnet(network, compartment: str, wanted: str | None) -> str:
    if wanted:
        return wanted
    subnets = [s for s in network.list_subnets(compartment).data if not s.prohibit_public_ip_on_vnic]
    if not subnets:
        sys.exit("No public subnet: create one with Networking > Virtual cloud networks > Start VCN Wizard")
    log(f"subnet: {subnets[0].display_name}")
    return subnets[0].id


def public_ip(compute, network, compartment: str, instance_id: str) -> str | None:
    for att in compute.list_vnic_attachments(compartment, instance_id=instance_id).data:
        vnic = network.get_vnic(att.vnic_id).data
        if vnic.public_ip:
            return vnic.public_ip
    return None


def report(ip: str | None, how: str) -> None:
    url = f"https://{ip.replace('.', '-')}.sslip.io" if ip else "(no public IP yet)"
    log(f"{how}. Public IP: {ip}. GigBid URL once setup finishes (~10 min after first boot): {url}")
    summary(f"### GigBid VM {how.lower()}\n\n- Public IP: `{ip}`\n- URL: {url}\n- SSH: `ssh ubuntu@{ip}`")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="DEFAULT")
    ap.add_argument("--subnet")
    ap.add_argument("--ssh-key", type=Path, default=Path.home() / ".ssh/id_ed25519.pub")
    ap.add_argument("--user-data", type=Path, help="first-boot script (cloud-init)")
    ap.add_argument("--every", type=int, default=60, help="seconds between rounds")
    ap.add_argument("--rounds", type=int, default=0, help="stop after this many rounds (0 = until success)")
    ap.add_argument("--dry-run", action="store_true", help="check credentials, image, subnet; launch nothing")
    a = ap.parse_args()

    config = oci.config.from_file(profile_name=a.profile)
    compartment = config["tenancy"]          # root compartment
    identity, compute = oci.identity.IdentityClient(config), oci.core.ComputeClient(config)
    network = oci.core.VirtualNetworkClient(config)

    existing = [i for i in compute.list_instances(compartment, display_name=NAME).data if i.lifecycle_state in ALIVE]
    if existing:
        report(public_ip(compute, network, compartment, existing[0].id), f"Already exists ({existing[0].lifecycle_state})")
        return

    ads = [ad.name for ad in identity.list_availability_domains(compartment).data]
    image, subnet = pick_image(compute, compartment), pick_subnet(network, compartment, a.subnet)
    ssh = os.environ.get("SSH_PUBLIC_KEY") or a.ssh_key.read_text()
    metadata = {"ssh_authorized_keys": ssh.strip()}
    if a.user_data:
        metadata["user_data"] = base64.b64encode(a.user_data.read_bytes()).decode()
    log(f"availability domains: {ads}")
    if a.dry_run:
        log(f"dry run OK: ssh key {len(metadata['ssh_authorized_keys'])} chars, "
            f"user_data {len(metadata.get('user_data', ''))} chars (base64); nothing launched")
        return

    attempt = 0
    while not a.rounds or attempt < a.rounds:
        attempt += 1
        ocpus, gb = SHAPES[(attempt - 1) % len(SHAPES)]   # one shape per round: Oracle answers 429 to bursts
        for ad in ads:
            details = oci.core.models.LaunchInstanceDetails(
                availability_domain=ad, compartment_id=compartment, display_name=NAME, shape=SHAPE,
                shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=ocpus, memory_in_gbs=gb),
                source_details=oci.core.models.InstanceSourceViaImageDetails(image_id=image, boot_volume_size_in_gbs=50),
                create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=subnet, assign_public_ip=True),
                metadata=metadata)
            try:
                inst = compute.launch_instance(details).data
            except (oci.exceptions.ConnectTimeout, oci.exceptions.RequestException) as e:
                log(f"#{attempt} network error, retrying: {str(e)[:80]}")
                continue
            except oci.exceptions.ServiceError as e:
                msg = f"{e.code} {e.message}".lower()
                if any(r in msg for r in RETRYABLE) or e.status in (429, 500):
                    log(f"#{attempt} {ad} {ocpus} OCPU/{gb} GB: {e.message[:80]}")
                    continue
                raise
            log(f"LAUNCHED {inst.id} ({ocpus} OCPU / {gb} GB) in {ad}; waiting for RUNNING...")
            oci.wait_until(compute, compute.get_instance(inst.id), "lifecycle_state", "RUNNING", max_wait_seconds=900)
            report(public_ip(compute, network, compartment, inst.id), f"Launched ({ocpus} OCPU / {gb} GB)")
            return
        time.sleep(a.every)
    log(f"No capacity after {attempt} rounds")
    summary(f"No Oracle capacity after {attempt} rounds; the next scheduled run tries again.")
    sys.exit(3)


if __name__ == "__main__":
    main()
