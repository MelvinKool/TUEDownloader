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

parser = argparse.ArgumentParser()
parser.add_argument('url')
parser.add_argument('--config', default='/etc/tuedownloader/tuedownloader.cfg')
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

if not r.ok:
    raise Exception('Request failed, got http status code {}'.format(r.status_code))

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
    raise Exception('Login post form url not found')

loginform_url_params = urllib.parse.parse_qs(
            urllib.parse.urlparse(loginform_post_url).query
        )
try:
    saml_request_param = loginform_url_params['SAMLRequest']
except KeyError:
    raise Exception('SAMLRequest not found')

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
        raise Exception(
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

# TODO

videopage = s.get(pageurl,
    headers={
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })

href_idx = videopage.text.find('window.location.href')
vpage_s = videopage.text.find('\'', href_idx)
# TODO check if found, bounds etc.
vpage_e = videopage.text.find('\'', vpage_s + 1)
video_ret_url = videopage.text[vpage_s + 1: vpage_e]

video_ret = s.get(video_ret_url,
    headers={
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })


# TODO duplicate code
r = do_saml_response(video_ret.text)

mediasite_info_s = r.text.find('window.mediasitePageInfo')
mediasite_info_s2 = r.text.find('player-presentation', mediasite_info_s)
mediasite_info_url_s = r.text.find('url: ', mediasite_info_s2)
mediasite_info_url_s2 = r.text.find('\'', mediasite_info_url_s) + 1
mediasite_info_url_e = r.text.find('\',', mediasite_info_url_s2)
mediasite_info_url = r.text[mediasite_info_url_s2:mediasite_info_url_e]

r = s.get(
    mediasite_info_url,
    headers={
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })

videopage_soup = BeautifulSoup(r.text, 'html.parser')
found_resource_ids = videopage_soup.find_all('div', {'id': 'ResourceId'})
resource_id  = None
for found_r_id in found_resource_ids:
    resource_id = found_r_id.text.strip()
    # check if text is not empty
    if not resource_id:
        continue

if not resource_id:
    raise Exception('Did not find the resource id')

# # Get #ResourceId

payload = {"getPlayerOptionsRequest": {
    "ResourceId": resource_id,
    "QueryString": "",
    "UseScreenReader": False,
    "UrlReferrer": ""}}

headers = {
    'Content-type': 'application/json',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'User-Agent': user_agent
}

playeroptions_url = urllib.parse.urljoin(
            pageurl,
            '/Mediasite/PlayerService/PlayerService.svc/json/GetPlayerOptions'
        )
r = s.post(
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

for i, video_url in enumerate(video_urls):
    file_name = "download_{}.mp4".format(i)
    with open(file_name, "wb") as f:
            print("Downloading {} saving to {}".format(video_url, file_name))
            response = requests.get(video_url, stream=True)
            total_length = response.headers.get('content-length')

            if total_length is None: # no content length header
                f.write(response.content)
            else:
                dl = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=4096):
                    dl += len(data)
                    f.write(data)
                    done = int(50 * dl / total_length)
                    sys.stdout.write("\r[%s%s]" % ('=' * done, ' ' * (50-done)) )
                    sys.stdout.flush()
