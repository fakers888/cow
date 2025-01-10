import os
import pathlib

from config import conf


class TmpDir(object):
    """A temporary directory that is deleted when the object is destroyed."""

    # 定义基础路径和URL路径
    tmpFilePath = pathlib.Path("./pic/tmp/")
    urlPath = "pic/tmp"  # URL访问路径

    def __init__(self):
        pathExists = os.path.exists(self.tmpFilePath)
        if not pathExists:
            os.makedirs(self.tmpFilePath)

    def path(self):
        return str(self.tmpFilePath) + "/"
    
    def url_path(self):
        """返回用于URL的路径部分"""
        return self.urlPath
