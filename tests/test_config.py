import pytest
from cinescrapper.config import ScraperConfig


def test_config_validation():
    ScraperConfig(batch_size=1).validate()
    with pytest.raises(ValueError):
        ScraperConfig(batch_size=0).validate()
