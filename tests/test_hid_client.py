import pytest

from lily58lp_manager import hid_client


class FakeInterface:
    def __init__(self) -> None:
        self.written: bytes | None = None
        self.closed = False

    def write(self, report: bytes) -> int:
        self.written = report
        return len(report)

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
    assert interface.written == bytes([0x00, 0x88]) + b"abc" + b"\0" * 28
    assert interface.closed is True


def test_hid_client_rejects_payloads_larger_than_the_report() -> None:
    oversized_payload = bytes(hid_client.REPORT_LENGTH)

    try:
        hid_client.HidClient().send(oversized_payload)
    except ValueError as error:
        assert "at most" in str(error)
    else:
        raise AssertionError("an oversized payload must not be written")


@pytest.mark.parametrize("payload", [b"", bytes(range(31)), b"QWERTY", b"DVORAK"])
def test_one_way_reports_preserve_all_payload_bytes(monkeypatch, payload) -> None:
    interface = FakeInterface()
    client = hid_client.HidClient()
    monkeypatch.setattr(client, "_open_interface", lambda: interface)
    assert client.send(payload)
    assert interface.written is not None
    assert len(interface.written) == 33
    assert interface.written[:2] == b"\x00\x88"
    assert interface.written[2:] == payload.ljust(31, b"\0")
    assert interface.closed


@pytest.mark.parametrize("layout", ["QWERTY", "DVORAK"])
def test_layer_commands_use_one_way_framing(monkeypatch, layout) -> None:
    interface = FakeInterface()
    client = hid_client.HidClient()
    monkeypatch.setattr(client, "_open_interface", lambda: interface)
    assert client.send_layer(layout)
    assert interface.written == b"\x00\x88" + layout.encode().ljust(31, b"\0")
    assert interface.closed


@pytest.mark.parametrize("written", [0, 32, -1])
def test_short_writes_fail_and_release_interface(monkeypatch, written) -> None:
    interface = FakeInterface()
    client = hid_client.HidClient()
    monkeypatch.setattr(client, "_open_interface", lambda: interface)
    monkeypatch.setattr(interface, "write", lambda report: written)
    assert not client.send(b"abc")
    assert interface.closed


def test_write_errors_release_interface(monkeypatch) -> None:
    interface = FakeInterface()
    client = hid_client.HidClient()
    monkeypatch.setattr(client, "_open_interface", lambda: interface)

    def fail(report):
        raise OSError("disconnected")

    monkeypatch.setattr(interface, "write", fail)
    assert not client.send(b"abc")
    assert interface.closed
