from app.ingest.normalize import html_to_text, normalize_url, titles_similar


def test_normalize_url_strips_tracking_www_and_slash():
    a = normalize_url("https://www.Example.com/post/?utm_source=x&b=2&a=1#frag")
    b = normalize_url("http://example.com/post?a=1&b=2")
    assert a == b == "example.com/post?a=1&b=2"


def test_titles_similar():
    assert titles_similar("Apple unveils new M5 chip", "Apple unveils new M5 chip!")
    assert not titles_similar("Apple unveils new M5 chip", "Rust 2.0 released")


def test_html_to_text_keeps_links_and_code():
    out = html_to_text('<p>Hi <a href="https://a.test">there</a></p><pre><code>x = 1</code></pre>')
    assert "there (https://a.test)" in out
    assert "```\nx = 1\n```" in out
