class ResallocIBMCloudException(Exception):
    """Base exception class for Resalloc IBM Cloud errors."""
    pass


class PowerVSException(ResallocIBMCloudException):
    """Base exception class for PowerVS errors."""


class PowerVSNotFoundException(PowerVSException):
    """Exception raised when a PowerVS resource is not found."""
    pass


class PowerVSInvalidNameException(PowerVSException):
    """Exception raised when a PowerVS resource name is invalid."""
    pass
