"""
List all IBM Cloud instances that are in Deleting state
"""

from resalloc_ibm_cloud.helpers import get_service
from resalloc_ibm_cloud.argparsers import default_arg_parser
from resalloc_ibm_cloud.constants import LIMIT


def main():
    """Entrypoint to the script."""

    opts = default_arg_parser().parse_args()
    cmd = f"source {opts.token_file} ; echo $IBMCLOUD_API_KEY"
    service = get_service(cmd, opts)

    instances = service.list_instances(limit=LIMIT).result["instances"]
    for server in instances:
        # Resalloc works with underscores, which is not allowed in IBM Cloud
        if server["status"] == "deleting":
            print(f"{server['id']} {server['name']}")
