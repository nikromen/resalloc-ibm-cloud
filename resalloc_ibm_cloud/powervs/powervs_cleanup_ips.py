"""
Helper script for cleaning up orphaned network interfaces (ports) from
PowerVS subnets.
"""

import logging

from resalloc_ibm_cloud.argparsers import powervs_cleanup_ips_parser
from resalloc_ibm_cloud.helpers import setup_logging
from resalloc_ibm_cloud.powervs.credentials import get_powervs_credentials
from resalloc_ibm_cloud.powervs.client import PowerVSClient


logger = logging.getLogger(__name__)


def _get_active_instance_ids(client: PowerVSClient) -> set[str]:
    instances = client.list_instances()
    return {inst["pvmInstanceID"] for inst in instances if inst.get("pvmInstanceID")}


def cleanup_network_interfaces(
    client: PowerVSClient,
    network_ids: list[str],
) -> None:
    """
    Delete orphaned network interfaces (ports) that are not attached to any
    active VM instance.
    """
    active_ids = _get_active_instance_ids(client)

    logger.info("Found %d active instance(s)", len(active_ids))

    for network_id in network_ids:
        interfaces = client.list_network_interfaces(network_id)
        logger.info(
            "Network %s: found %d network interface(s)",
            network_id, len(interfaces),
        )

        orphaned = 0
        for iface in interfaces:
            instance_ref = iface.get("instance")
            instance_id = instance_ref.get("instanceID") if instance_ref else None
            if instance_id and instance_id in active_ids:
                continue

            orphaned += 1
            logger.info(
                "Deleting orphaned network interface %s (ip=%s) from network %s",
                iface["id"], iface.get("ipAddress", "?"), network_id,
            )

            client.delete_network_interface(network_id, iface["id"])

        logger.info(
            "Network %s: deleted %d orphaned interface(s)", network_id, orphaned,
        )


def main() -> None:
    """Entrypoint to the script."""
    opts = powervs_cleanup_ips_parser().parse_args()
    setup_logging(opts.log_level)

    credentials = get_powervs_credentials(opts.token_file, opts.crn)
    client = PowerVSClient(credentials)
    cleanup_network_interfaces(client, opts.network_id)
