import os
import re

from cinescrapper import cine_constants


def fetch_cache_dir(request_type: str) -> str:
    cache_dir = os.getcwd() + "/site_cache/"
    if request_type is not None:
        if request_type == cine_constants.TYPE_MOVIE:
            cache_dir = cache_dir + "movies/"
        elif request_type == cine_constants.TYPE_SOUNDTRACK:
            cache_dir = cache_dir + "soundtrack/"
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    return cache_dir


def find_year(_title):
    """
    Find the Year from the Title.
    Extract the digits.
    :param _title:
    :return:
    """
    match = re.search("\\d+", _title)
    if match:
        return match.group()
    return None


def sum_dict_values(_dict):
    """
    Get the total of the dictionary values
    :param _dict:
    :return:
    """
    total = 0
    for val in _dict.values():
        total = total + val
    return total
