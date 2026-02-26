"""
ArgumentParser getters on one place, this simplifies generating manual pages.
"""

import argparse
import sys

if 313 > sys.version_info.major * 100 + sys.version_info.minor:
    DEPRECATED_OPTION = {}
else:
    DEPRECATED_OPTION = {"deprecated": True}


def _pfx(name):
    return "resalloc-ibm-cloud-" + name


def _default_arg_parser(prog=None):
    """
    The part that every resalloc-ibm-cloud utility needs
    """

    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument(
        "--token-file", help="Path to IBM cloud token file", required=True
    )
    parser.add_argument("--log-level", default="info")
    return parser


def _default_arg_parser_vpc(prog=None):
    parser = _default_arg_parser(prog=prog)
    parser.add_argument(
        "--zone",
        help="default IBM Cloud zone. e.g. jp-tok, us-east, us-west, ...",
        dest="region",
        **DEPRECATED_OPTION,
    )
    parser.add_argument(
        "--region",
        help="default IBM Cloud zone. e.g. jp-tok, us-east, us-west, ...",
    )
    return parser

def _default_arg_parser_powervs(prog=None):
    parser = _default_arg_parser(prog=prog)
    parser.add_argument(
        "--crn",
        help="CRN of the PowerVS instance, used to get credentials",
        required=True,
    )
    return parser


def _add_common_create_args(parser_create):
    """
    Add arguments common to all create commands
    """
    parser_create.add_argument("name")
    parser_create.add_argument("--playbook", help="Path to playbook", required=True)
    parser_create.add_argument("--image-uuid", required=True, help="UUID of the image to use")
    return parser_create


def _add_tags_argument(parser):
    """
    Add tags argument to a parser
    """
    parser.add_argument(
        "--tags",
        type=str,
        nargs="+",
        help="Space separated list of key:value tags, e.g. app:copr",
    )
    return parser


def vm_arg_parser():
    """
    Parser for the resalloc-ibm-cloud-vm utility.
    """
    parser = _default_arg_parser_vpc(prog=_pfx("vm"))

    subparsers = parser.add_subparsers(dest="subparser")
    subparsers.required = True
    parser_create = subparsers.add_parser(
        "create", help="Create an instance in IBM Cloud"
    )
    _add_common_create_args(parser_create)
    parser_create.add_argument("--vpc-id", required=True)
    parser_create.add_argument("--security-group-id", required=True)
    parser_create.add_argument("--ssh-key-id", required=True)
    parser_create.add_argument("--instance-type", help="e.g. cz2-2x4", required=True)

    f_ip_group = parser_create.add_mutually_exclusive_group()

    f_ip_group.add_argument("--floating-ip-name", default=None)
    f_ip_group.add_argument("--floating-ip-uuid", default=None)
    f_ip_group.add_argument(
        "--no-floating-ip", action="store_true", help="Don't use floating IPs (for VPN)"
    )
    f_ip_group.add_argument("--floating-ip-uuid-in-subnet", nargs=2,
                            metavar=("SUBNET-ID", "FLOATING-IP-UUID"),
                            action='append', help=(
        "Add a Floating IP UUID into the list of IPs that can be used for the "
        "corresponding subnet ID.  Depending on the $RESALLOC_ID_IN_POOL (given "
        "by Resalloc server) the script assigns the newly started machine "
        "n-th IP from the list."
    ))
    parser_create.add_argument(
        "--subnets-ids",
        type=str,
        nargs="+",
        help=(
            "Space separated list of ZONE:SUBNET_ID pairs.  The ZONE "
            "must be a valid ZONE ID within the specified --region ("
            "e.g., 'eu-es-2' within 'eu-es' region)."
        ),
        required=True,
    )
    parser_create.add_argument(
        "--additional-volume-size",
        type=int,
        help="Allocate additional volume of given size in GB",
        default=160,
    )
    parser_create.add_argument(
        "--resource-group-id", help="Resource group id, get it from `$ ibmcloud resources`"
    )
    _add_tags_argument(parser_create)
    parser_delete = subparsers.add_parser(
        "delete", help="Delete instance by it's name from IBM Cloud"
    )
    parser_delete.add_argument("name")
    subparsers.add_parser(
        "delete-free-floating-ips", help="Clean all IPs without an assigned VM"
    )
    return parser


def _list_arg_parser(prog=None):
    """
    Parser for listing utilities
    """
    parser = _default_arg_parser_vpc(prog=prog)
    parser.add_argument("--pool")
    return parser

def list_deleting_vms_parser():
    """ parser for listing vms """
    return _list_arg_parser(prog=_pfx("list-deleting-vms"))

def list_vms_parser():
    """ parser for listing deleting vms """
    return _list_arg_parser(prog=_pfx("list-vms"))

def list_deleting_volumes_parser():
    """ parser for listing vms """
    return _default_arg_parser_vpc(prog=_pfx("list-deleting-volumes"))


def powervs_arg_parser():
    """
    Parser for the resalloc-ibm-cloud-powervs-vm utility.
    """
    parser = _default_arg_parser_powervs(prog=_pfx("powervs-vm"))

    subparsers = parser.add_subparsers(dest="subparser")
    subparsers.required = True
    
    parser_create = subparsers.add_parser(
        "create", help="Create a PowerVS instance in IBM Cloud"
    )
    _add_common_create_args(parser_create)
    parser_create.add_argument(
        "--ssh-key-name", required=True, help="Name of the SSH key to use for the instance"
    )
    parser_create.add_argument(
        "--processors", type=float, required=True, help="Number of processors (CPU cores)"
    )
    parser_create.add_argument(
        "--processor-type",
        choices=["dedicated", "shared", "capped"], 
        help="Processor type (dedicated, shared, or capped)",
        default="shared",
    )
    parser_create.add_argument(
        "--ram", type=float, required=True, help="RAM memory in GB"
    )
    parser_create.add_argument(
        "--network-id", type=str, nargs="+", help="ID of the network to attach to the instance"
    )
    parser_create.add_argument(
        "--storage-type",
        choices=["tier1", "tier3"],
        default="tier3",
        help="Storage tier type (tier1 for SSD, tier3 for HDD)",
    )
    parser_create.add_argument(
        "--volumes",
        type=str,
        nargs="+",
        help="Additional volumes to attach in format 'name:size_gb:type'"
    )
    _add_tags_argument(parser_create)
    parser_create.add_argument(
        "--system-type",
        choices=["s922", "e980"],
        help="Machine type (s922, e980)",
        default="s922",
    )
    parser_create.add_argument(
        "--no-rmc",
        action="store_true",
        help="Do not wait for Resource Monitoring and Control to be ready"
    )
    parser_create.add_argument(
        "--storage-pool",
        type=str,
        help="Storage pool to create the volumes and VMs in (if not specified, default is used)",
    )

    parser_delete = subparsers.add_parser(
        "delete", help="Delete PowerVS instance by its name from IBM Cloud"
    )
    parser_delete.add_argument("name")
    
    return parser


def powervs_list_vms_parser():
    """
    Parser for listing PowerVS VMs
    """
    parser = _default_arg_parser_powervs(prog=_pfx("powervs-list-vms"))
    parser.add_argument(
        "--pool",
        help="Pool ID prefix to filter instances",
        required=True,
    )
    return parser


def powervs_list_deleting_vms_parser():
    """
    Parser for listing deleting PowerVS VMs
    """
    parser = _default_arg_parser_powervs(prog=_pfx("powervs-list-deleting-vms"))
    return parser


def powervs_cleanup_ips_parser():
    """
    Parser for the resalloc-ibm-cloud-powervs-cleanup-ips utility.
    """
    parser = _default_arg_parser_powervs(prog=_pfx("powervs-cleanup-ips"))
    parser.add_argument(
        "--network-id",
        type=str,
        nargs="+",
        required=True,
        help="One or more network (subnet) IDs to clean up orphaned IPs from",
    )
    return parser
