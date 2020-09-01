#!/usr/bin/env python3
"""
Caution: this code is really ugly.
I don't really care atm, it's late and it works.
"""
import requests
from bs4 import BeautifulSoup
import urllib
import json
import sys
import configparser
import argparse
import os
import youtube_dl
from tuedownloader import util


class TUEDownloaderException(Exception):
    def __init__(self, message, errors=None):

        # Call the base class constructor with the parameters it needs
        super().__init__(message)

        # Now for your custom code...
        self.errors = errors


class TUEDownloader(object):

    def __init__(self, username, password, user_agent):
        self.username = username
        self.password = password
        self.user_agent = user_agent
        self.session = None
        self.supported_mime_types = [
            "video/mp4",
            "video/x-mpeg-dash",
            "video/x-mp4-fragmented",
        ]

    def get_session(self, login_url):
        self.session = requests.Session()
        r = self.session.get(
          urllib.parse.urljoin(login_url, '/'),
          headers={
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
          },
        )

        if not r.ok:
            raise TUEDownloaderException(
                    'Request failed, got http status code {}'.format(r.status_code)
                    )

        getpage_soup = BeautifulSoup(r.text, 'html.parser')

        get_login_form = getpage_soup.find_all('form', {'id': 'options'})

        loginform_post_url = None
        for login_form in get_login_form:
            try:
                loginform_post_url = login_form['action']
                break
            except KeyError:
                continue

        if not loginform_post_url:
            raise TUEDownloaderException('Login post form url not found')

        r = self.session.post(
          loginform_post_url,
          headers={
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://sts.tue.nl',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
          },
          data={
            'UserName': self.username,
            'Password': self.password,
            'AuthMethod': 'FormsAuthentication',
          },
        )

        r = self.do_saml_response(r.text)

    def do_saml_response(self, saml_response_text):
        """
        Posts the SAML stuff
        """
        getpage_soup = BeautifulSoup(saml_response_text, 'html.parser')
        saml_response_form = getpage_soup.find('form')
        saml_post_url = saml_response_form['action'].strip()
        saml_response = None
        saml_relay_state = None

        for saml_r_input in saml_response_form.find_all('input'):
            try:
                if saml_r_input['name'] == 'SAMLResponse':
                    saml_response = saml_r_input['value']
                elif saml_r_input['name'] == 'RelayState':
                    saml_relay_state = saml_r_input['value']
            except KeyError:
                continue

        if not (saml_response and saml_relay_state):
            raise TUEDownloaderException(
                    'saml_response or saml_relay_state missing in SAML response'
                )

        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://sts.tue.nl',
            'Connection': 'keep-alive',
            'Referer': 'https://sts.tue.nl/',
            'Upgrade-Insecure-Requests': '1',
            'TE': 'Trailers',
        }

        data = {
          'SAMLResponse': saml_response,
          'RelayState': saml_relay_state
        }

        r = self.session.post(saml_post_url, headers=headers, data=data)
        return r




    def saml_inbetween_page(self, inbetweenpage):
        href_idx = inbetweenpage.find('window.location.href')
        vpage_s = inbetweenpage.find('\'', href_idx)
        # TODO check if found, bounds etc.
        vpage_e = inbetweenpage.find('\'', vpage_s + 1)
        page_ret_url = inbetweenpage[vpage_s + 1: vpage_e]

        return self.session.get(
                page_ret_url,
                headers={
                    'User-Agent': self.user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                })

    def download_video_showcase(self, videourl, video_root='.'):
        r = self.session.get(
            videourl,
            headers={
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })

        videopage_soup = BeautifulSoup(r.text, 'html.parser')
        found_resource_ids = videopage_soup.find_all('div', {'id': 'ResourceId'})
        resource_id = None
        for found_r_id in found_resource_ids:
            resource_id = found_r_id.text.strip()
            # check if text is not empty
            if not resource_id:
                continue

        if not resource_id:
            raise TUEDownloaderException('Did not find the resource id')

        # # Get #ResourceId

        payload = {"getPlayerOptionsRequest": {
            "ResourceId": resource_id,
            "QueryString": "",
            "UseScreenReader": False,
            "UrlReferrer": ""}}

        playeroptions_url = urllib.parse.urljoin(
                    videourl,
                    '/Mediasite/PlayerService/PlayerService.svc/json/GetPlayerOptions'
                )
        r = self.session.post(
            playeroptions_url,
            data=json.dumps(payload),
            headers={
                'Content-type': 'application/json',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'User-Agent': self.user_agent
            })

        player_options = json.loads(r.text)
        # Contains a dict with available mimetypes and location urls
        video_urls = {}
        for stream in player_options['d']['Presentation']['Streams']:
            if 'VideoUrls' not in stream.keys():
                continue

            for video_url in stream['VideoUrls']:
                try:
                    mime_type = video_url['MimeType'] 
                    location = video_url['Location'] 
                    if mime_type in video_urls:
                        video_urls[mime_type].add(location)
                    else:
                        video_urls[mime_type] = {location}
                except KeyError:
                    continue

        video_title = util.escape_file(videopage_soup.title.text)
        video_dir = os.path.join(video_root, video_title)
        if not os.path.isdir(video_dir):
            os.makedirs(video_dir)

        # Select which mimetype to use
        for mime_type in self.supported_mime_types:
            if mime_type in video_urls:
                print(f"[i] Selected mime_type: {mime_type}")
                supported_urls = video_urls[mime_type]
                break

        # TODO; This only allows for 1 mime_type per lecture,
        # If for example, slides/screencast is recorded in another
        # format, this won't work.
        # However, I don't think that's a common case (exluding slide png's)

        for i, video_url in enumerate(supported_urls):
            file_name = os.path.join(video_dir, "download_{}.mp4".format(i))
            if os.path.isfile(file_name):
                print('{} already found, skipping...'.format(file_name))
                continue

            ytdl_opts = {
                'outtmpl': file_name
            }
            try:
                with youtube_dl.YoutubeDL(ytdl_opts) as ytdl:
                    # TODO; Move this download out of the for loop.
                    # YTDL takes a list of videos as argument, which it
                    # Can download in parallel
                    ytdl.download([video_url])

            except Exception:
                if os.path.isfile(file_name):
                    os.remove(file_name)
                raise TUEDownloaderException(
                        'Downloading file {} failed, removed file {}.'.format(
                            video_url,
                            file_name)
                    )
        return video_dir

    def download_video(self, videourl, video_root):
        videopage = self.session.get(
                videourl,
                headers={
                    'User-Agent': self.user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                })

        video_ret = self.saml_inbetween_page(videopage.text)
        r = self.do_saml_response(video_ret.text)

        mediasite_info_s = r.text.find('window.mediasitePageInfo')
        mediasite_info_s2 = r.text.find(
                    'player-presentation',
                    mediasite_info_s
                )
        mediasite_info_url_s = r.text.find('url: ', mediasite_info_s2)
        mediasite_info_url_s2 = r.text.find('\'', mediasite_info_url_s) + 1
        mediasite_info_url_e = r.text.find('\',', mediasite_info_url_s2)
        mediasite_info_url = r.text[mediasite_info_url_s2:mediasite_info_url_e]

        self.download_video_showcase(
                mediasite_info_url,
                video_root=video_root
            )

    def download_channel(self, channel_url, channel_root):
        # Get title from page.title
        saml_resp = self.session.get(
            channel_url,
            headers={
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })

        saml_request = self.saml_inbetween_page(saml_resp.text)
        channel_resp = self.do_saml_response(saml_request.text)

        getchannel_soup = BeautifulSoup(channel_resp.text, 'html.parser')
        channel_title = getchannel_soup.title.text
        print('Channel: {}'.format(channel_title))

        channel_app_info_s = channel_resp.text.find('Application.set(\'data\'')

        showcase_id_s = channel_resp.text.find(
                    '\'ShowcaseId\':', channel_app_info_s
                )
        showcase_id_s = channel_resp.text.find(
                    '\'',
                    showcase_id_s + len('\'ShowcaseId\':')
                ) + 1
        showcase_id_e = channel_resp.text.find('\'', showcase_id_s)
        showcase_id = channel_resp.text[showcase_id_s:showcase_id_e]

        sfapikey_s = channel_resp.text.find('\'ApiKey\':', channel_app_info_s)
        sfapikey_s = channel_resp.text.find(
                    '\'',
                    sfapikey_s + len('\'ApiKey\':')
                ) + 1
        sfapikey_e = channel_resp.text.find('\'', sfapikey_s)
        sfapikey = channel_resp.text[sfapikey_s:sfapikey_e]

        channel_id_s = channel_resp.text.find('\'ChannelId\':', channel_app_info_s)
        channel_id_s = channel_resp.text.find(
                    '\'',
                    channel_id_s + len('\'ChannelId\':')
                ) + 1
        channel_id_e = channel_resp.text.find('\'', channel_id_s)
        channel_id = channel_resp.text[channel_id_s:channel_id_e]

        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer':
            'https://videocollege.tue.nl/Mediasite/Showcase/{}/Channel/{}'.format(
                showcase_id,
                channel_id),
            'sfapikey': sfapikey,
            'ShowcaseId': showcase_id,
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
        }

        # TODO ('$top', '16'), looping
        params = (
            ('$filter',
                '(Status eq \'Viewable\' or Status eq \'Live\' or (Status eq \'Record\' and IsLiveEnabled eq true) or (Status eq \'OpenForRecord\' and IsLiveEnabled eq true)) and IsApproved eq true'),
            ('$orderby', 'RecordDate desc'),
            ('$select', 'full'),
            ('$top', '999'),
            ('$skip', '0'),
            ('excludeduplicates', 'true'),
        )

        # # channel id is in url (eb....4d)
        channel_json_resp = self.session.get(
                'https://videocollege.tue.nl/Mediasite/api/v1/ShowcaseChannels(%27{}%27)/Presentations'.format(
                    channel_id),
                headers=headers,
                params=params)

        # Make directory
        this_channel_root = os.path.join(
                    channel_root,
                    util.escape_dir(channel_title)
                )
        if not os.path.isdir(this_channel_root):
            os.makedirs(this_channel_root)

        channel_json = json.loads(channel_json_resp.text)
        for channel_vid in channel_json['value']:
            if '#Play' not in channel_vid.keys():
                continue

            channel_vid_play = channel_vid['#Play']
            if 'target' not in channel_vid_play.keys():
                continue

            try:
                self.download_video_showcase(
                        channel_vid_play['target'],
                        video_root=this_channel_root)
            except TUEDownloaderException as e:
                print(
                    'Downloading {} failed: {}'.format(
                        channel_vid_play['target'],
                        str(e))
                    )
                continue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument(
            '--config',
            default='/etc/tuedownloader/tuedownloader.cfg'
        )
    parser.add_argument('--channel', action='store_true')
    parser.add_argument('--root', default='.')
    args = parser.parse_args()

    pageurl = args.url

    cfg = configparser.ConfigParser()
    cfg.read(args.config)

    user_agent = cfg['Downloader']['UserAgent']

    username = cfg['Credentials']['Username']
    password = cfg['Credentials']['Password']

    tue_downloader = TUEDownloader(username, password, user_agent)

    tue_downloader.get_session(pageurl)
    if args.channel:
        tue_downloader.download_channel(pageurl, args.root)
    else:
        tue_downloader.download_video(pageurl, args.root)


if __name__ == "__main__":
    main()
