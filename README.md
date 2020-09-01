# TUEDownloader
Tool to download lectures from TU Eindhoven.
Use this tool at your own risk!
I'm not responsible for copyright violations you make by using this tool in any way.

## Installation
To install, run `sudo python3 setup.py install`.
Run `sudo mkdir /etc/tuedownloader` and `sudo cp example/example.cfg /etc/tuedownloader/tuedownloader.cfg`.
Set the permissions on the config file, edit credentials with `sudoedit /etc/tuedownloader/tuedownloader.cfg` and you are ready to go.

## Downloading a lecture
To download a lecture, run `tuedownloader https://videocollege.tue.nl/Mediasite/Showcase/<hash>/Presentation/<hash>`

## Downloading a channel
To download a lecture, run `tuedownloader --channel https://videocollege.tue.nl/Mediasite/Showcase/<hash>/Channel/<hash>`

## Contributors
Melvin Kool (project owner)
RickdeJager
