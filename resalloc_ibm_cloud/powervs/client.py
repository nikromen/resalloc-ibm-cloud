"""
PowerVS API client implementation (at least what we need).
"""

import json
import logging

import backoff
import requests

from resalloc_ibm_cloud.powervs.credentials import PowerVSCredentials

logger = logging.getLogger(__name__)


class PowerVSClient:
    """
    Client for interacting with the IBM Cloud PowerVS API
    """

    def __init__(self, credentials: PowerVSCredentials) -> None:
        self.credentials = credentials
        self.cloud_instance_id = credentials.cloud_instance_id

    def _is_server_error(self, exception):
        """
        Determine if an exception is due to a server error.
        Server errors (5xx) should be retried, client errors (4xx) should not.

        Args:
            exception: The exception to check

        Returns:
            True if exception represents a server error, False otherwise
        """
        if isinstance(exception, requests.HTTPError):
            return 500 <= exception.response.status_code < 600
        return isinstance(exception, (requests.ConnectionError, requests.Timeout))

    @backoff.on_exception(
        backoff.expo,
        requests.RequestException,
        max_time=300,
        # only retry on server errors
        giveup=lambda e: not PowerVSClient._is_server_error(PowerVSClient, e),
        # 2, 4, 8, 16, ...
        factor=2,
        jitter=backoff.full_jitter,
        # custom warning log on backoff for more informative retries
        on_backoff=lambda details: logger.warning(
            "Retrying request due to %s: %s. Retry %d in %.1fs. Total elapsed time: %.1fs",
            details["exception"].__class__.__name__,
            str(details["exception"]),
            details["tries"],
            details["wait"],
            details["elapsed"],
        ),
    )
    def request(
        self,
        method: str,
        path: str,
        params: dict = None,
        json_data: dict = None,
        broker: bool = False,
    ) -> dict:
        """
        Make a request to the PowerVS API with automatic retry for server errors

        The method will automatically retry on server errors (5xx) and connection issues
        for up to 5 minutes using an exponential backoff strategy with jitter.
        Client errors (4xx) are not retried as they typically indicate a problem with
        the request that won't be resolved by retrying.

        Args:
            method: HTTP method
            path: API path
            params: Query parameters
            json_data: JSON body data
            broker: Whether to use the broker API

        Returns:
            Response JSON

        Raises:
            requests.HTTPError: If the request fails with a non-server error or
                if all retries are exhausted
            requests.RequestException: For other request-related errors after
                retries are exhausted
        """
        base_url = (
            self.credentials.broker_url if broker else self.credentials.service_url
        )

        # set prefix path for powervs API workspace
        if not broker and not path.startswith(
            f"/cloud-instances/{self.cloud_instance_id}"
        ):
            path = f"/cloud-instances/{self.cloud_instance_id}{path}"

        url = f"{base_url}{path}"
        logger.debug("Request %s %s", method, url)

        if json_data:
            logger.debug("Request body: %s", json.dumps(json_data, indent=4))

        response = requests.request(
            method, url, headers=self.credentials.headers, params=params, json=json_data
        )

        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error("API request failed: %s %s - %s", method, url, response.text)
            raise

        if response.content:
            resp = response.json()
            logger.debug("Received response: %s", json.dumps(resp, indent=4))
            return resp

        return {}

    def create_instance(self, instance_data: dict) -> dict:
        """
        Create a new PowerVS instance

        Args:
            instance_data: Instance creation data

        Returns:
            Created instance details
        """
        logger.info(
            "Creating PowerVS instance with body: %s",
            json.dumps(instance_data, indent=4),
        )

        return self.request(
            "POST",
            "/pvm-instances",
            json_data=instance_data,
        )

    def get_instance(self, instance_id: str) -> dict:
        """
        Get a PowerVS instance by ID

        Args:
            instance_id: Instance ID

        Returns:
            Instance details
        """
        return self.request("GET", f"/pvm-instances/{instance_id}")

    def delete_instance(
        self,
        instance_id: str,
        delete_data_volumes: bool = False,
    ) -> None:
        """
        Delete a PowerVS instance

        Args:
            instance_id: Instance ID
            delete_data_volumes: Whether to delete associated data volumes
        """
        self.request(
            "DELETE",
            f"/pvm-instances/{instance_id}",
            json_data={"delete_data_volumes": delete_data_volumes},
        )

    def list_instances(self) -> list[dict]:
        """
        List all PowerVS instances

        Returns:
            List of instances
        """
        response = self.request("GET", "/pvm-instances")
        return response.get("pvmInstances", [])

    def create_volume(self, volume_data: dict) -> dict:
        """
        Create a new PowerVS volume

        Args:
            volume_data: Volume creation body

        Returns:
            Created volume details
        """
        logger.info(
            "Creating PowerVS volume with body: %s", json.dumps(volume_data, indent=4)
        )
        return self.request(
            "POST",
            "/volumes",
            json_data=volume_data,
        )

    def update_volume(
        self,
        volume_id: str,
        json_data: dict = None,
    ) -> dict:
        """
        Update a PowerVS volume

        Args:
            volume_id: Volume ID to update
            json_data: Updated volume data

        Returns:
            Updated volume details
        """
        logger.info("Updating PowerVS volume with ID: %s", volume_id)
        return self.request(
            "PUT",
            f"/volumes/{volume_id}",
            json_data=json_data,
        )

    def delete_volume(self, volume_id: str) -> None:
        """
        Delete a PowerVS volume

        Args:
            volume_id: Volume ID to delete
        """
        logger.info("Deleting PowerVS volume with ID: %s", volume_id)
        self.request(
            "DELETE",
            f"/volumes/{volume_id}",
        )

    def detach_volume(
        self,
        instance_id: str,
        volume_id: str,
    ) -> None:
        """
        Detach a volume from a PowerVS instance

        Args:
            instance_id: Instance ID
            volume_id: Volume ID to detach
        """
        logger.info(
            "Detaching volume %s from instance %s", volume_id, instance_id
        )
        self.request(
            "DELETE",
            f"/pvm-instances/{instance_id}/volumes/{volume_id}",
        )

    def list_volumes(self) -> list[dict]:
        """
        List all PowerVS volumes

        Returns:
            List of volumes
        """
        return self.request("GET", "/volumes")
