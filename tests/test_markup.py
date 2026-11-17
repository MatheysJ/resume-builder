from resume_builder.markup import inline


def test_bold_and_links():
    html = inline("Uso **Java** no [projeto](https://example.com/x?a=1&b=2)")

    assert "<strong>Java</strong>" in html
    assert '<a href="https://example.com/x?a=1&amp;b=2">projeto</a>' in html


def test_html_in_yaml_is_escaped():
    assert inline("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_unsafe_url_keeps_only_the_label():
    assert inline("[clique](javascript:alert%281%29)") == "clique"


def test_mailto_and_tel_are_allowed():
    assert 'href="mailto:a@b.com"' in inline("[e-mail](mailto:a@b.com)")
    assert 'href="tel:+5511900000000"' in inline("[fone](tel:+5511900000000)")
