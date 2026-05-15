from __future__ import annotations

import unittest

from browser.render import render_message_body_html


class RenderTests(unittest.TestCase):
    def test_basic_markdown_emphasis_renders(self) -> None:
        html = render_message_body_html("Normal text with **Course Overview** and *details*.")
        self.assertIn("<strong>Course Overview</strong>", html)
        self.assertIn("<em>details</em>", html)

    def test_inline_tex_parentheses_are_preserved_for_mathjax(self) -> None:
        html = render_message_body_html(r"Inline math: \(g(x)=x+1\) and $f(x)=x^2$.")
        self.assertIn(r"\(g(x)=x+1\)", html)
        self.assertIn(r"\(f(x)=x^2\)", html)
        self.assertNotIn(r"\1g(x)=x+1\1", html)

    def test_math_isolated_from_markdown_processing(self) -> None:
        html = render_message_body_html(
            r"Alternative Verification Using AM-GM: set $a=b=c=\frac{1}{3}$ and compare with **boundary** cases."
        )
        self.assertIn("Alternative Verification Using AM-GM:", html)
        self.assertIn(r"\(a=b=c=\frac{1}{3}\)", html)
        self.assertIn("<strong>boundary</strong>", html)
        self.assertNotIn("<em>Using AM-GM</em>", html)


if __name__ == "__main__":
    unittest.main()
