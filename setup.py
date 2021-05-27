from setuptools import setup, find_packages
import os

def set_cfg_path():
    dirname = os.path.dirname(os.path.abspath(__file__))
    path_downloadformatpy = os.path.join(dirname,"tuedownloader", "download_format.py")
    path_downloadpy = os.path.join(dirname,"tuedownloader", "download.py")
    path_config = os.path.join(dirname,"tuedownloader", "tuedownloader.cfg")
    download_file = open(path_downloadpy,"w")
    target_string = "default='/etc/tuedownloader/tuedownloader.cfg'"

    with open(path_downloadformatpy) as f:
        for line in f:
            if target_string not in line:
                download_file.write(line)
            else:
                download_file.write(f"            default=r'{path_config}'\n")
    download_file.close()

set_cfg_path()

setup(
    name="TUEDownloader",
    version="0.1",
    packages=find_packages(),
    install_requires=['beautifulsoup4', 'requests', 'youtube_dl', 'ffmpeg-python'],
    entry_points = {
        "console_scripts": [
            "tuedownloader = tuedownloader.download:main"
            ]
    }
)