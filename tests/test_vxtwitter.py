import pytest

from cogs import vxtwitter

@pytest.fixture
def mock_bot() -> object:
    return object()

@pytest.fixture()
def cog():
    return vxtwitter.Vxtwitter(mock_bot)

@pytest.mark.parametrize(("input_text", "output"), [
    pytest.param("https://x.com/Test_Account/status/1935493771721517678?t=YhMjRFnyI_Y_cPdrA9zIoA&s=19",
                 "https://vxtwitter.com/Test_Account/status/1935493771721517678",
                 id="links_get_reduced_to_bare_minimum"),
    pytest.param("something https://x.com/test/status/123 something",
                 "https://vxtwitter.com/test/status/123",
                 id="only_links_are_returned"),
    pytest.param("https://mobile.twitter.com/test/status/123",
                 "https://vxtwitter.com/test/status/123",
                 id="mobile_links_work_as_well"),
    pytest.param("https://x.com/test/status/123\nhttps://twitter.com/test/status/123",
                 "https://vxtwitter.com/test/status/123",
                 id="only_return_unique_links"),
    pytest.param("https://x.com/test/status/123\nhttps://twitter.com/test/status/456",
                 "https://vxtwitter.com/test/status/123 https://vxtwitter.com/test/status/456",
                 id="multiple_unique_links_are_returned_separated_by_whitespaces"),
    pytest.param("https://vxtwitter.com/test/status/123",
                 None,
                 id="vxtwitter_links_are_ignored"),
    pytest.param("https://xcancel.com/test/status/123",
                 None,
                 id="xcancel_links_are_ignored"),
    pytest.param("just some text",
                 None,
                 id="nothing_returned_if_there_are_no_links"),
])
def test_generate_vxtwitter_links(cog, input_text, output):
    assert cog.generate_vxtwitter_links(input_text) == output
