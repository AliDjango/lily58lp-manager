from lily58lp_manager import hid_client


class FakeInterface:
    def __init__(self) -> None:
        self.written: bytes | None = None
        self.closed = False

    def write(self, report: bytes) -> None:
        self.written = report

    def close(self) -> None:
        self.closed = True


def test_hid_client_frames_and_closes_report(monkeypatch) -> None:
    interface = FakeInterface()
    monkeypatch.setattr(
        hid_client.hid,
        "enumerate",
        lambda vendor_id, product_id: [
            {
                "usage_page": hid_client.USAGE_PAGE,
                "usage": hid_client.USAGE,
                "path": b"keyboard",
            }
        ],
    )
    monkeypatch.setattr(hid_client.hid, "Device", lambda path: interface)

    assert hid_client.HidClient().send(b"abc") is True
    assert interface.written == bytes([hid_client.REPORT_ID]) + b"abc" + b"\0" * 28
    assert interface.closed is True


def test_hid_client_rejects_payloads_larger_than_the_report() -> None:
    oversized_payload = bytes(hid_client.REPORT_LENGTH)

    try:
        hid_client.HidClient().send(oversized_payload)
    except ValueError as error:
        assert "at most" in str(error)
    else:
        raise AssertionError("an oversized payload must not be written")
