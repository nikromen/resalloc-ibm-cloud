"""
List all IBM Cloud PowerVS instances.
"""

import os
import sys

from resalloc_ibm_cloud.powervs.credentials import get_powervs_credentials
from resalloc_ibm_cloud.powervs.client import PowerVSClient
from resalloc_ibm_cloud.argparsers import powervs_list_vms_parser


def list_vms(client: PowerVSClient, pool_id: str) -> set[str]:
    """
    List all PowerVS instances for the specified pool.

    Args:
        client: PowerVS client
        pool_id: Pool ID to filter instances

    Returns:
        Set of resource names that match the pool ID
    """
    resources = set()
    for instance in client.list_instances():
        instance_name = instance["serverName"]
        if instance_name.startswith(pool_id):
            resources.add(instance_name)

    return resources


def list_volumes_associated_vms(client: PowerVSClient, pool_id: str) -> set[str]:
    """
    List all volumes and get their associated VMs.

    Args:
        client: PowerVS client
        pool_id: Pool ID to filter VMs

    Returns:
        Set of VMs names associated with the specified volumes
    """
    vms = set()
    for volume in client.list_volumes():
        volume_name = volume["volumeID"]
        if volume_name.startswith(pool_id):
            # the dropped suffix is underscore something (_volume)
            vms.add(volume_name.rsplit("_volume", 1)[0])

    return vms


def main():
    """Entrypoint to the script."""
    opts = powervs_list_vms_parser().parse_args()

    pool_id = opts.pool or os.getenv("RESALLOC_POOL_ID")
    if not pool_id:
        sys.stderr.write("Specify pool ID by --pool or $RESALLOC_POOL_ID\n")
        sys.exit(1)

    credentials = get_powervs_credentials(opts.token_file, opts.crn)
    client = PowerVSClient(credentials)

    resources = list_vms(client, pool_id) | list_volumes_associated_vms(client, pool_id)
    for name in resources:
        print(name)
