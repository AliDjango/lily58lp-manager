from lily58lp_manager.layout import layer_for_layout


def test_layer_for_layout_uses_qwerty_for_persian() -> None:
    assert layer_for_layout(1, 1) == "QWERTY"
    assert layer_for_layout(0, 1) == "DVORAK"
