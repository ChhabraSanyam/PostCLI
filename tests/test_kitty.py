from postcli.kitty import cursor_to, delete_image, fit_placement, place_png, supports_graphics


def test_kitty_protocol_sequences_are_chunked_and_placed():
    sequence = place_png(b"x" * 5000, image_id=42, columns=30, rows=20)

    assert sequence.startswith("\x1b_Ga=T,f=100,i=42,c=30,r=20,C=1,z=1,q=2,m=1;")
    assert "\x1b_Gm=0;" in sequence
    assert cursor_to(8, 4) == "\x1b[4;8H"
    assert delete_image(42) == "\x1b_Ga=d,d=I,i=42,q=2\x1b\\"


def test_kitty_support_detection():
    assert supports_graphics({"TERM": "xterm-kitty"})
    assert supports_graphics({"KITTY_WINDOW_ID": "1"})
    assert supports_graphics({"POSTCLI_IMAGE_PROTOCOL": "kitty"})
    assert not supports_graphics({"TERM": "xterm-256color"})


def test_kitty_placement_preserves_image_aspect_ratio():
    columns, rows, offset_x, offset_y = fit_placement(80, 40, 1080, 1350, 0.5)

    assert (columns, rows) == (64, 40)
    assert (offset_x, offset_y) == (8, 0)
