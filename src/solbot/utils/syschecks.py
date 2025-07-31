import os
import time
import ntplib


def ntp_drift() -> float:
    c = ntplib.NTPClient()
    resp = c.request('pool.ntp.org', version=3)
    return resp.offset


def check_ntp(max_drift: float = 1.0) -> None:
    try:
        drift = abs(ntp_drift())
        if drift > max_drift:
            raise RuntimeError(f'NTP drift {drift:.2f}s exceeds limit')
    except Exception as e:
        raise RuntimeError(f'NTP check failed: {e}')


def disk_iops_test(path: str) -> float:
    start = time.perf_counter()
    for _ in range(100):
        with open(path, 'wb') as fh:
            fh.write(b'0')
        os.remove(path)
    return 100 / (time.perf_counter() - start)
