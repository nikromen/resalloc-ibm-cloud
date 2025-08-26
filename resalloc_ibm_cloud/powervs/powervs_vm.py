"""
Start a new VM in IBM Cloud Power Virtual Server.
"""

import logging
import subprocess
import sys
import time
from time import sleep
from typing import Any, Optional

import backoff
from requests import HTTPError
import requests

from resalloc_ibm_cloud.argparsers import powervs_arg_parser
from resalloc_ibm_cloud.exceptions import PowerVSInvalidNameException, PowerVSNotFoundException
from resalloc_ibm_cloud.helpers import run_playbook, setup_logging, wait_for_ssh
from resalloc_ibm_cloud.powervs.credentials import get_powervs_credentials
from resalloc_ibm_cloud.powervs.client import PowerVSClient


logger = logging.getLogger(__name__)


class PowerVSVMManager:
    def __init__(self, client: PowerVSClient) -> None:
        self.client = client

    @staticmethod
    def _build_instance_base_body(name: str, options: Any) -> dict:
        instance_body = {
            "serverName": name,
            "imageID": options.image_uuid,
            "processors": options.processors,
            "procType": options.processor_type,
            "memory": options.ram,
            "networks": [
                {"networkID": network_id}
                for network_id in options.network_id
                if network_id and network_id.strip()
            ],
            "sysType": options.system_type,
            "keyPairName": options.ssh_key_name,
        }

        # optional parameters
        if getattr(options, "tags", None) is not None:
            instance_body["userTags"] = list(options.tags)

        if getattr(options, "pinPolicy", None) is not None:
            instance_body["pinPolicy"] = options.pin_policy

        if getattr(options, "storage_type", None) is not None:
            instance_body["storageType"] = options.storage_type

        return instance_body

    def _create_volumes_with_tags(
            self, volumes: list[dict], tags: Optional[list[str]]
    ) -> list[str]:
        if not volumes:
            return []

        if tags:
            for volume in volumes:
                volume["userTags"] = tags

        ids = []
        for volume in volumes:
            resp = self.client.create_volume(volume)
            volume_id = resp.get("volumeID")
            logger.debug("Created volume %s with ID %s", volume["name"], volume_id)
            ids.append(volume_id)

        return ids

    def _create_instance(self, instance_body: dict, no_rmc: bool) -> dict:
        instance = self.client.create_instance(instance_body)
        # they say it's dict in the docs, but it's actually a list of one element lol xd
        instance_id = instance[0]["pvmInstanceID"]
        logger.info("PowerVS instance creation initiated. Instance ID: %s", instance_id)

        # wait for the instance to be active, in powervs this may be even 5 or 10 minutes
        # before the instance is even _listed_ in the cloud as ready. After that part, the
        # subnet will be attached and the IP address will be available.
        return self._wait_for_instance_active(instance_id=instance_id, no_rmc=no_rmc)

    @staticmethod
    def _extract_ip_address(instance: dict) -> str:
        networks = instance.get("networks", [])
        if not networks:
            raise PowerVSNotFoundException("Instance does not have any networks attached")

        ip_address = networks[0].get("ip")
        if not ip_address:
            raise PowerVSNotFoundException("No IP address found for the instance")

        logger.info("Instance IP address: %s", ip_address)
        return ip_address

    def create_vm(self, name: str, options: Any) -> str:
        """
        Create a new VM instance in PowerVS

        Args:
            name: Instance name
            options: Options with VM configuration

        Returns:
            IP address of the created instance
        """
        instance_body = self._build_instance_base_body(name, options)

        volumes = self._parse_volumes(getattr(options, "volumes", []))
        volume_ids = self._create_volumes_with_tags(volumes, getattr(options, "tags", None))

        instance_body["volumeIDs"] = volume_ids

        try:
            instance = self._create_instance(instance_body, options.no_rmc)
        except Exception:
            logger.error("Instance creation failed, cleaning up allocated volumes...")
            sleep(20)  # give IBM Cloud a while to process the volumes
            for volume_id in volume_ids:
                try:
                    self._delete_volume_with_backoff(volume_id)
                    logger.info("Cleaned up orphaned volume with ID %s", volume_id)
                except Exception as e:
                    logger.error("Failed to clean up volume %s: %s", volume_id, str(e))
            raise

        ip_address = self._extract_ip_address(instance)
        wait_for_ssh(ip_address)

        run_playbook(host=ip_address, playbook_path=options.playbook)

        return ip_address

    # this is just a simple retry wrapper, because IBM Cloud freaks out for a while
    # once the volume is deleted, returning random errors when trying to delete it...
    # it should work after a few retries (up to 30 seconds)
    @backoff.on_exception(
        backoff.constant,
        requests.RequestException,
        max_time=120,
        interval=10,
    )
    def _delete_volume_with_backoff(self, volume_id: str) -> None:
        self.client.delete_volume(volume_id)
        logger.info("Deleted volume with ID %s", volume_id)

    def delete_vm(self, name: str) -> None:
        """
        Delete a VM instance by name

        Args:
            name: Instance name
        """
        logger.info("Deleting PowerVS instance %s", name)

        instances = self.client.list_instances()
        instance_id = None

        for instance in instances:
            if instance["serverName"] == name:
                instance_id = instance["pvmInstanceID"]
                break

        if not instance_id:
            logger.warning("No instance found with name %s", name)
            return

        instance_information = self.client.get_instance(instance_id)
        volume_ids = instance_information.get("volumeIDs", [])

        # the data volumes tends to remain undeleted even if the delete_instance
        # call is with delete_data_volumes, so this needs to be assured manually
        for volume_id in volume_ids:
            try:
                self.client.detach_volume(instance_id, volume_id)
                logger.info("Detached volume with ID %s from instance %s", volume_id, instance_id)
                self._delete_volume_with_backoff(volume_id)
            except HTTPError as e:
                logger.error("Failed to delete volume %s: %s", volume_id, str(e))

        self.client.delete_instance(
            instance_id,
            delete_data_volumes=True,
        )
        logger.info(
            "PowerVS instance %s (ID: %s) deletion initiated",
            name,
            instance_id,
        )

    def _parse_volumes(self, volumes_list: list[str]) -> list[dict]:
        """
        Parse volume specifications from a list of strings.

        Each string should be in the format "name:size[:diskType]".
        """
        result = []
        for vol_spec in volumes_list:
            parts = vol_spec.split(":")
            if len(parts) < 2:
                logger.warning("Invalid volume specification: %s", vol_spec)
                continue

            volume = {
                "name": parts[0],
                "size": float(parts[1]),
            }

            if len(parts) > 2:
                volume["diskType"] = parts[2]

            result.append(volume)

        return result

    def _wait_for_instance_active(
        self, instance_id: str, no_rmc: bool, timeout: int = 1200, interval: int = 10,
    ) -> dict:
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(
                    f"Instance did not become active within {timeout} seconds"
                )

            instance = self.client.get_instance(instance_id)
            status = instance.get("status")

            logger.info("Instance status: %s", status)

            if status == "ACTIVE" and self._wait_for_health_or_ssh(instance, no_rmc, timeout):
                logger.info("Instance is active and healthy")
                return instance
            elif status in ["ERROR", "FAILED"]:
                raise RuntimeError(f"Instance creation failed with status: {status}")

            sleep(interval)

    # Wait for the instance to be healthy and ready... even after it is active, the ssh often
    # does not work immediately for some reason. In my experience, it takes about 10 minutes.
    # But sometimes this will hang forever if the instance network is configured
    # via some hacks that break RMC
    # https://www.ibm.com/docs/en/powervc/2.0.3?topic=solutions-newly-deployed-virtual-machine-status-shows-warning
    @classmethod
    def _wait_for_health_or_ssh(cls, instance: dict, no_rmc: bool, timeout: int) -> bool:
        if no_rmc:
            # check at least if we can ssh
            try:
                ip_address = cls._extract_ip_address(instance)
                wait_for_ssh(ip_address, timeout)
                return True
            except PowerVSNotFoundException:
                logger.warning("IP address not found (yet?) for instance %s", instance.get("id"))
                return False
            except subprocess.CalledProcessError as e:
                raise TimeoutError("SSH did not become available in time") from e

        health_status = instance.get("health", {}).get("status")
        logger.debug("Waiting for instance health status: %s", health_status)
        return health_status == "OK"


def main() -> int:
    """
    Main entry point for PowerVS VM management.

    Returns:
        Exit code
    """
    opts = powervs_arg_parser().parse_args()
    if len(opts.name) > 46:
        raise PowerVSInvalidNameException("Instance name must be 47 characters or fewer")

    setup_logging(opts.log_level)

    try:
        credentials = get_powervs_credentials(opts.token_file, opts.crn)
        client = PowerVSClient(credentials)
        vm_manager = PowerVSVMManager(client)

        if opts.subparser == "create":
            try:
                ip_address = vm_manager.create_vm(opts.name, opts)
                print(ip_address)
            except Exception as e:
                # this mainly handles the post VM creation cleanup
                logger.error(
                    "Failed to create VM: %s; trying to remove allocated resources...",
                    str(e)
                )
                sleep(20)  # give IBM Cloud a while
                vm_manager.delete_vm(opts.name)
                raise
        elif opts.subparser == "delete":
            vm_manager.delete_vm(opts.name)
        else:
            logger.error("Unknown subcommand: %s", opts.subparser)
            sys.exit(1)

        sys.exit(0)

    except Exception as e:
        logger.exception("Error in PowerVS VM management: %s", str(e))
        sys.exit(1)
