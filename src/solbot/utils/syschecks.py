import os
import time
import logging
import ntplib


def ntp_drift() -> float:
    c = ntplib.NTPClient()
    resp = c.request('pool.ntp.org', version=3)
    return resp.offset


logger = logging.getLogger(__name__)


def check_ntp(max_drift: float = 1.0) -> None:
    try:
        drift = abs(ntp_drift())
    except Exception as e:
        logger.warning("NTP check failed: %s", e)
        return
    if drift > max_drift:
        raise RuntimeError(f'NTP drift {drift:.2f}s exceeds limit')


def disk_iops_test(path: str) -> float:
    """Measure disk write IOPS by repeatedly writing a file.

    The parent directory is created if it does not already exist so that callers
    may freely supply paths under non-existent directories.
    """

    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    start = time.perf_counter()
    for _ in range(100):
        with open(path, 'wb') as fh:
            fh.write(b'0')
        os.remove(path)
    return 100 / (time.perf_counter() - start)
