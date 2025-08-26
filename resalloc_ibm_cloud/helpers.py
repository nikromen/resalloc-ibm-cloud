import logging
import subprocess
import datetime
from argparse import Namespace
import sys

from ibm_vpc import VpcV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator


def get_service(opts: Namespace):
    """
    Taking command-line argument options, load the IBM Cloud token file and
    perform authentication against given IBM Cloud end-point.  We expect that
    the token file is a shell file that defines $IBMCLOUD_API_KEY variable
    inside.  Use techniques like:

        echo -n "Please enter your IBM Cloud key: "
        read -sr IBMCLOUD_API_KEY
        echo

    Input options:
        opts.token_file -> file to read and process with shell
        opts.region     -> zone in IBM Cloud, e.g. 'jp-tok'
    """

    cmd = f"source {opts.token_file} ; echo $IBMCLOUD_API_KEY"
    output = subprocess.check_output(cmd, shell=True)
    token = output.decode("utf-8").strip().rsplit("\n", maxsplit=1)[-1]
    authenticator = IAMAuthenticator(token)
    now = datetime.datetime.now()
    service = VpcV1(now.strftime("%Y-%m-%d"), authenticator=authenticator)
    service.set_service_url(f"https://{opts.region}.iaas.cloud.ibm.com/v1")
    return service


def wait_for_ssh(floating_ip, timeout=240):
    """
    Wait for SSH to be available on the given floating IP address.
    
    Args:
        floating_ip: The floating IP address to check
        timeout: Maximum time to wait in seconds (default is 240)
    """
    cmd = [
        "resalloc-wait-for-ssh",
        "--log",
        "debug",
        "--timeout",
        str(timeout),
        floating_ip,
    ]
    subprocess.check_call(cmd, stdout=sys.stderr)


def run_playbook(host: str, playbook_path: str) -> None:
    """
    Run ansible-playbook against the given hostname
    
    Args:
        host: IP address or hostname of the instance
        playbook_path: Path to the Ansible playbook
    """
    cmd = ["ansible-playbook", playbook_path, "--inventory", f"{host},"]
    subprocess.check_call(cmd, stdout=sys.stderr, stdin=subprocess.DEVNULL)


def setup_logging(log_level="info"):
    """
    Logging configuration for all resalloc-ibm-cloud scripts.

    Args:
        log_level: Logging level as string (default: "info")
    """
    root_logger = logging.getLogger(__name__)
    root_logger.handlers.clear()

    logging.basicConfig(level=log_level.upper(), datefmt="[%H:%M:%S]")

    root_logger.debug(f"Log level set to {log_level}")
