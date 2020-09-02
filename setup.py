from setuptools import setup, find_packages

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
