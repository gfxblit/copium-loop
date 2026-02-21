import unittest

from copium_loop.shell import _clean_chunk


class TestShellSecurity(unittest.TestCase):
    def test_clean_chunk_csi(self):
        """Test cleaning of CSI sequences (e.g. colors, cursor movement)."""
        # Red text
        self.assertEqual(_clean_chunk("\x1b[31mHello"), "Hello")
        # Bold text
        self.assertEqual(_clean_chunk("\x1b[1mBold"), "Bold")
        # Complex CSI: 256 colors
        self.assertEqual(_clean_chunk("\x1b[38;5;160mColor"), "Color")
        # Cursor movement (potential for overwriting logs)
        self.assertEqual(_clean_chunk("\x1b[2J\x1b[HReset"), "Reset")

    def test_clean_chunk_osc(self):
        """Test cleaning of OSC sequences (e.g. window title, hyperlinks)."""
        # Window title: \x1B]0;Title\x07
        self.assertEqual(_clean_chunk("\x1b]0;My Title\x07Content"), "Content")
        # Hyperlink: \x1B]8;;https://example.com\x1B\\Link\x1B]8;;\x1B\\
        # Note: \x1B\\ is ST (String Terminator)
        self.assertEqual(
            _clean_chunk("\x1b]8;;https://example.com\x1b\\Link\x1b]8;;\x1b\\"), "Link"
        )

    def test_clean_chunk_other_sequences(self):
        """Test cleaning of other escape sequences."""
        # Fe sequence: \x1B(0 (switch to line drawing charset)
        # Note: \x1B( is likely an Fs sequence (ESC + intermediate + final),
        # but G0/G1 designation \x1B(0 is common.
        # My proposed regex handles Fs/Fp/nF: \x1B[ -/][@-~]
        # \x1B matches ESC
        # ( is 0x28 which is in [ -/]
        # 0 is 0x30 which is in [@-~]
        self.assertEqual(_clean_chunk("\x1b(0Line"), "Line")

    def test_clean_chunk_plain_text(self):
        """Test that plain text is unaffected."""
        self.assertEqual(_clean_chunk("Hello World"), "Hello World")
        self.assertEqual(_clean_chunk("1234567890"), "1234567890")
        self.assertEqual(_clean_chunk("!@#$%^&*()_+"), "!@#$%^&*()_+")

    def test_clean_chunk_mixed(self):
        """Test mixed content."""
        content = "Start \x1b[32mGreen\x1b[0m Middle \x1b]0;Hidden\x07End"
        self.assertEqual(_clean_chunk(content), "Start Green Middle End")


if __name__ == "__main__":
    unittest.main()
