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
from tuedownloader import util

parser = argparse.ArgumentParser()
parser.add_argument('url')
parser.add_argument('--config', default='/etc/tuedownloader/tuedownloader.cfg')
parser.add_argument('--channel', action='store_true')
parser.add_argument('--root', default='.')
args = parser.parse_args()

pageurl = args.url

cfg = configparser.ConfigParser()
cfg.read(args.config)

user_agent = cfg['Downloader']['UserAgent']

username = cfg['Credentials']['Username']
password = cfg['Credentials']['Password']

s = requests.Session()
r = s.get(
  urllib.parse.urljoin(pageurl, '/'),
  headers={
    'User-Agent': user_agent,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
  },
)


class TUEDownloaderException(Exception):
    def __init__(self, message, errors=None):

        # Call the base class constructor with the parameters it needs
        super().__init__(message)

        # Now for your custom code...
        self.errors = errors


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

loginform_url_params = urllib.parse.parse_qs(
            urllib.parse.urlparse(loginform_post_url).query
        )
try:
    saml_request_param = loginform_url_params['SAMLRequest']
except KeyError:
    raise TUEDownloaderException('SAMLRequest not found')

r = s.post(
  loginform_post_url,
  headers={
    'User-Agent': user_agent,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://sts.tue.nl',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
  },
  data={
    'UserName': username,
    'Password': password,
    'AuthMethod': 'FormsAuthentication',
  },
)


def do_saml_response(saml_response_text):
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
        'User-Agent': user_agent,
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

    r = s.post(saml_post_url, headers=headers, data=data)
    return r


r = do_saml_response(r.text)


def saml_inbetween_page(session, inbetweenpage):
    href_idx = inbetweenpage.find('window.location.href')
    vpage_s = inbetweenpage.find('\'', href_idx)
    # TODO check if found, bounds etc.
    vpage_e = inbetweenpage.find('\'', vpage_s + 1)
    page_ret_url = inbetweenpage[vpage_s + 1: vpage_e]

    return session.get(
            page_ret_url,
            headers={
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })


def download_video_showcase(videourl, session, video_root='.'):
    r = session.get(
        videourl,
        headers={
            'User-Agent': user_agent,
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
    r = session.post(
        playeroptions_url,
        data=json.dumps(payload),
        headers={
            'Content-type': 'application/json',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'User-Agent': user_agent
        })

    player_options = json.loads(r.text)
    video_urls = set()
    # TODO mimetype checks
    for stream in player_options['d']['Presentation']['Streams']:
        if 'VideoUrls' not in stream.keys():
            continue

        for video_url in stream['VideoUrls']:
            try:
                video_urls.add(video_url['Location'])
            except KeyError:
                continue

    video_title = util.escape_file(videopage_soup.title.text)
    video_dir = os.path.join(video_root, video_title)
    if not os.path.isdir(video_dir):
        os.makedirs(video_dir)

    for i, video_url in enumerate(video_urls):
        file_name = os.path.join(video_dir, "download_{}.mp4".format(i))
        if os.path.isfile(file_name):
            print('{} already found, skipping...'.format(file_name))
            continue

        try:
            with open(file_name, "wb") as f:
                print(
                    "Downloading {} saving to {}".format(
                        video_url,
                        file_name)
                    )
                response = requests.get(video_url, stream=True)
                total_length = response.headers.get('content-length')

                if total_length is None:  # no content length header
                    f.write(response.content)
                else:
                    dl = 0
                    total_length = int(total_length)
                    for data in response.iter_content(chunk_size=4096):
                        dl += len(data)
                        f.write(data)
                        done = int(50 * dl / total_length)
                        sys.stdout.write(
                                "\r[%s%s]" % ('=' * done, ' ' * (50-done))
                            )
                        sys.stdout.flush()
                    print('\r\n')
        except Exception:
            if os.path.isfile(file_name):
                os.remove(file_name)
            raise TUEDownloaderException(
                    'Downloading file {} failed, removed file {}.'.format(
                        video_url,
                        file_name)
                )
    return video_dir


def download_video(session, videourl, video_root):
    videopage = session.get(
            videourl,
            headers={
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })

    video_ret = saml_inbetween_page(session, videopage.text)
    r = do_saml_response(video_ret.text)

    mediasite_info_s = r.text.find('window.mediasitePageInfo')
    mediasite_info_s2 = r.text.find('player-presentation', mediasite_info_s)
    mediasite_info_url_s = r.text.find('url: ', mediasite_info_s2)
    mediasite_info_url_s2 = r.text.find('\'', mediasite_info_url_s) + 1
    mediasite_info_url_e = r.text.find('\',', mediasite_info_url_s2)
    mediasite_info_url = r.text[mediasite_info_url_s2:mediasite_info_url_e]

    download_video_showcase(mediasite_info_url, session, video_root=video_root)


def download_channel(session, channel_url, channel_root):
    # Get title from page.title
    saml_resp = session.get(
        channel_url,
        headers={
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    saml_request = saml_inbetween_page(session, saml_resp.text)
    channel_resp = do_saml_response(saml_request.text)

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
        'User-Agent': user_agent,
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

    params = (
        ('$filter',
            '(Status eq \'Viewable\' or Status eq \'Live\' or (Status eq \'Record\' and IsLiveEnabled eq true) or (Status eq \'OpenForRecord\' and IsLiveEnabled eq true)) and IsApproved eq true'),
        ('$top', '16'),
        ('$orderby', 'RecordDate desc'),
        ('$select', 'full'),
        ('$skip', '0'),
        ('excludeduplicates', 'true'),
    )

    # # channel id is in url (eb....4d)
    channel_json_resp = session.get(
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
            download_video_showcase(
                    channel_vid_play['target'],
                    session,
                    video_root=this_channel_root)
        except TUEDownloaderException as e:
            print(
                'Downloading {} failed: {}'.format(
                    channel_vid_play['target'],
                    e.message)
                )
            continue


if args.channel:
    download_channel(s, pageurl, args.root)
else:
    download_video(s, pageurl, args.root)
