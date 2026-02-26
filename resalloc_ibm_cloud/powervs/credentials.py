"""
PowerVS credentials management.
"""

import subprocess
from dataclasses import dataclass

from ibm_cloud_sdk_core.authenticators import IAMAuthenticator


@dataclass
class PowerVSCredentials:
    """For storing PowerVS authentication credentials"""

    token: str
    crn: str

    @property
    def cloud_instance_id(self) -> str:
        """PowerVS cloud instance ID"""
        return self.crn.split(":")[7]

    @property
    def region(self) -> str:
        """PowerVS region from the CRN"""
        return self.crn.split(":")[5]

    @property
    def iaas_url(self) -> str:
        """Base URL for the PowerVS API in this region"""
        return f"https://{self.region}.power-iaas.cloud.ibm.com"

    @property
    def service_url(self) -> str:
        """PowerVS service URL for the region (/pcloud/v1 API path)"""
        return f"{self.iaas_url}/pcloud/v1"

    @property
    def v1_url(self) -> str:
        """PowerVS v1 API URL (/v1 - totally different API - no pcloud prefix)"""
        return f"{self.iaas_url}/v1"

    @property
    def broker_url(self) -> str:
        """PowerVS broker URL"""
        return f"{self.iaas_url}/broker/v1"

    @property
    def headers(self) -> dict[str, str]:
        """Request headers with authentication"""
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "CRN": self.crn,
            "Content-Type": "application/json",
        }


def get_powervs_credentials(token_file: str, crn: str) -> PowerVSCredentials:
    """
    Get PowerVS credentials from a token file

    Args:
        token_file: Path to the token (API key) file

    Returns:
        PowerVS credentials
    """
    cmd = f"source {token_file} ; echo $IBMCLOUD_API_KEY"
    output = subprocess.check_output(cmd, shell=True)
    api_key = output.decode("utf-8").strip().rsplit("\n", maxsplit=1)[-1]

    authenticator = IAMAuthenticator(api_key)

    return PowerVSCredentials(token=authenticator.token_manager.get_token(), crn=crn)
