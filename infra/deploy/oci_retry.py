"""Launch an Oracle Cloud Always Free ARM VM (VM.Standard.A1.Flex) for GigBid, retrying until capacity opens.

  uv run --with oci python infra/deploy/oci_retry.py            # uses ~/.oci/config (profile DEFAULT)
  uv run --with oci python infra/deploy/oci_retry.py --subnet ocid1.subnet...   # if you have several subnets

Stays inside the Always Free limits (A1: 4 OCPUs and 24 GB in total; boot volume 50 GB of the 200 GB).
Every 60 s it tries each availability domain with the shapes in SHAPES, largest first, and stops at the
first success: it waits for RUNNING and prints the public IP. "Out of host capacity" and 429s just wait.
Needs: ~/.oci/config (Console > My profile > API keys > Add API key), a VCN with a public subnet
(Networking > Virtual cloud networks > Start VCN Wizard > "VCN with Internet Connectivity"), and an SSH
public key (default ~/.ssh/id_ed25519.pub; create one with: ssh-keygen -t ed25519).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import oci

SHAPE = "VM.Standard.A1.Flex"
SHAPES = [(4, 24), (2, 12), (1, 6)]          # (OCPUs, GB): all within the Always Free allowance
RETRYABLE = ("out of host capacity", "out of capacity", "toomanyrequests", "internalerror")


def pick_image(compute, compartment: str) -> str:
    images = compute.list_images(compartment, operating_system="Canonical Ubuntu", operating_system_version="24.04",
                                 shape=SHAPE, sort_by="TIMECREATED", sort_order="DESC").data
    if not images:
        sys.exit("No Ubuntu 24.04 aarch64 image found for A1 in this region")
    print(f"image: {images[0].display_name}")
    return images[0].id


def pick_subnet(network, compartment: str, wanted: str | None) -> str:
    if wanted:
        return wanted
    subnets = [s for s in network.list_subnets(compartment).data if not s.prohibit_public_ip_on_vnic]
    if not subnets:
        sys.exit("No public subnet: create one with Networking > Virtual cloud networks > Start VCN Wizard")
    print(f"subnet: {subnets[0].display_name}")
    return subnets[0].id


def public_ip(compute, network, compartment: str, instance_id: str) -> str | None:
    for att in compute.list_vnic_attachments(compartment, instance_id=instance_id).data:
        vnic = network.get_vnic(att.vnic_id).data
        if vnic.public_ip:
            return vnic.public_ip
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="DEFAULT")
    ap.add_argument("--subnet")
    ap.add_argument("--ssh-key", type=Path, default=Path.home() / ".ssh/id_ed25519.pub")
    ap.add_argument("--every", type=int, default=60, help="seconds between rounds")
    a = ap.parse_args()

    config = oci.config.from_file(profile_name=a.profile)
    compartment = config["tenancy"]          # root compartment
    identity, compute = oci.identity.IdentityClient(config), oci.core.ComputeClient(config)
    network = oci.core.VirtualNetworkClient(config)
    ads = [ad.name for ad in identity.list_availability_domains(compartment).data]
    image, subnet = pick_image(compute, compartment), pick_subnet(network, compartment, a.subnet)
    ssh = a.ssh_key.read_text().strip()
    print(f"availability domains: {ads}")

    attempt = 0
    while True:
        attempt += 1
        for ad in ads:
            for ocpus, gb in SHAPES:
                details = oci.core.models.LaunchInstanceDetails(
                    availability_domain=ad, compartment_id=compartment, display_name="gigbid", shape=SHAPE,
                    shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=ocpus, memory_in_gbs=gb),
                    source_details=oci.core.models.InstanceSourceViaImageDetails(image_id=image,
                                                                                 boot_volume_size_in_gbs=50),
                    create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=subnet, assign_public_ip=True),
                    metadata={"ssh_authorized_keys": ssh})
                try:
                    inst = compute.launch_instance(details).data
                except (oci.exceptions.ConnectTimeout, oci.exceptions.RequestException) as e:
                    print(f"[{time.strftime('%H:%M:%S')}] network error, retrying: {str(e)[:80]}", flush=True)
                    time.sleep(30)
                    continue
                except oci.exceptions.ServiceError as e:
                    msg = f"{e.code} {e.message}".lower()
                    if any(r in msg for r in RETRYABLE) or e.status in (429, 500):
                        print(f"[{time.strftime('%H:%M:%S')}] #{attempt} {ad} {ocpus}/{gb}GB: {e.message[:80]}", flush=True)
                        time.sleep(10)   # spaced out: Oracle answers 429 to rapid retries
                        continue
                    raise
                print(f"LAUNCHED {inst.id} ({ocpus} OCPU / {gb} GB) in {ad}; waiting for RUNNING...", flush=True)
                oci.wait_until(compute, compute.get_instance(inst.id), "lifecycle_state", "RUNNING", max_wait_seconds=900)
                print(f"RUNNING. Public IP: {public_ip(compute, network, compartment, inst.id)}  (ssh ubuntu@<ip>)")
                return
        time.sleep(a.every)


if __name__ == "__main__":
    main()
