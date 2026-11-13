"""Configure database deployments for JSONBench experiments."""

import base64
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def couchbase_request(deployment, path, data=None):
    """Send a local management request without writing credentials to artifacts."""
    token = base64.b64encode(f"{deployment.username}:{deployment.password}".encode()).decode()
    request = Request(
        f"http://127.0.0.1:{deployment.port}{path}",
        data=None if data is None else urlencode(data).encode(),
        headers={"Authorization": f"Basic {token}"},
    )
    with urlopen(request, timeout=30) as response:
        body = response.read()
        return json.loads(body) if body else None


def configure_couchbase(deployment, config):
    """Set service quotas and give the travel bucket the full data quota."""
    quotas = {
        "memoryQuota": config["couchbase_data_mb"],
        "indexMemoryQuota": config["couchbase_index_mb"],
    }
    couchbase_request(deployment, "/pools/default", quotas)
    couchbase_request(
        deployment,
        "/pools/default/buckets/travel",
        {"ramQuotaMB": config["couchbase_data_mb"]},
    )
    actual = couchbase_request(deployment, "/pools/default")
    bucket = couchbase_request(deployment, "/pools/default/buckets/travel")
    if any(actual[key] != value for key, value in quotas.items()):
        raise RuntimeError("Couchbase service quotas do not match the configuration")
    if bucket["quota"]["ram"] != config["couchbase_data_mb"] * 1024**2:
        raise RuntimeError("Couchbase bucket quota does not match the configuration")
