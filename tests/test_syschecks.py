from solbot.utils.syschecks import disk_iops_test


def test_disk_iops_creates_missing_dir(tmp_path):
    path = tmp_path / "nested" / "iops.tmp"
    iops = disk_iops_test(str(path))
    assert iops > 0
    assert not path.exists()
