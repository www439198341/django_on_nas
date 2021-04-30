import base64
import json
import os
import socket
import time
from base64 import b64decode
from urllib.parse import urlsplit
from urllib.request import urlopen

import requests
import socks

from better_v2ray.models import SubscriptionModel
from django_on_nas.settings import logger
from local_settings import bwg, template, WAIT_RESTART, TIME_LIMIT, WEB_SPEED, DOWNLOAD_SPEED, VALID_PROTOCOL, \
    ONLINE_URLS


def gen_update_time(str_time):
    json_content = {'v': '', 'ps': '更新于:%s - by Flynn' % str_time, 'add': '', 'port': '', 'id': '', 'aid': '',
                    'net': '', 'type': '', 'host': '', 'path': '', 'tls': '', 'sni': ''}
    str_content = json.dumps(json_content)
    link_with_update_time = str(b'vmess://' + base64.b64encode(str_content.encode('utf-8')), encoding='utf-8')
    return link_with_update_time


def read_vmess(splited_url):
    try:
        url_netloc = splited_url.netloc
        json_content = json.loads(b64decode(url_netloc).decode('utf-8'))
        config = {"protocol": "vmess",
                  "settings": {
                      "vnext": [
                          {
                              "address": json_content.get('add'),
                              "port": int(json_content.get('port')),
                              "users": [
                                  {
                                      "id": json_content.get('id'),
                                      "alterId": int(json_content.get('aid')),
                                      "email": "t@t.tt",
                                      "security": "auto"
                                  }
                              ]
                          }
                      ]
                  },
                  "streamSettings": {
                      "network": json_content.get('net'),
                      "security": "tls",
                      "tlsSettings": {
                          "allowInsecure": False,
                          "serverName": json_content.get('host')
                      },
                      "wsSettings": {
                          "path": json_content.get('path'),
                          "headers": {
                              "Host": json_content.get('host')
                          }
                      }
                  }, }
        return config
    except Exception as e:
        logger.error(e)
        return None


def read_ss(splited_url):
    try:
        url_netloc = splited_url.netloc
        # 两种不同的编码方式
        if '@' in url_netloc:
            method_password = url_netloc.split('@')[0]
            method_password_decode = b64decode(method_password).decode('utf-8')
            method = method_password_decode.split(':')[0]
            password = method_password_decode.split(':')[1]
            add_port = url_netloc.split('@')[1]
            add = add_port.split(':')[0]
            port = int(add_port.split(':')[1])
        else:
            url_netloc = b64decode(url_netloc).decode('utf-8')
            method_password = url_netloc.split('@')[0]
            method = method_password.split(':')[0]
            password = method_password.split(':')[1]
            add_port = url_netloc.split('@')[1]
            add = add_port.split(':')[0]
            port = add_port.split(':')[1]
        config = {
            "protocol": "shadowsocks",
            "settings": {
                "servers": [
                    {
                        "address": add,
                        "method": method,
                        "ota": False,
                        "password": password,
                        "port": int(port),
                        "level": 1
                    }
                ]
            },
            "streamSettings": {
                "network": "tcp"
            },
        }
        return config
    except Exception as e:
        logger.error(e)
        return None


def read_trojan(splited_url):
    try:
        url_netloc = splited_url.netloc
        config = {"protocol": "trojan",
                  "settings": {
                      "servers": [
                          {
                              "address": splited_url.hostname,
                              "method": "chacha20",
                              "ota": False,
                              "password": url_netloc.split('@')[0],
                              "port": int(url_netloc.split(':')[1]),
                              "level": 1
                          }
                      ]
                  },
                  "streamSettings": {
                      "network": "tcp",
                      "security": "tls",
                      "tlsSettings": {
                          "allowInsecure": False
                      }
                  }, }
        return config
    except Exception as e:
        logger.error(e)
        return None


def read_vless(splited_url):
    try:
        query = splited_url.query.replace('%f', '/')
        params = query.split('&')
        params_json = {}
        for param in params:
            params_json[param.split('=')[0]] = param.split('=')[1]

        config = {"protocol": "vless",
                  "settings": {
                      "vnext": [
                          {
                              "address": splited_url.hostname,
                              "port": int(splited_url.port),
                              "users": [
                                  {
                                      "id": splited_url.username,
                                      "alterId": 64,
                                      "email": "t@t.tt",
                                      "security": "auto"
                                  }
                              ]
                          }
                      ]
                  },
                  "streamSettings": {
                      "network": params_json.get('type'),
                      "security": params_json.get('security'),
                      "tlsSettings": {
                          "allowInsecure": False,
                          "serverName": params_json.get('host')
                      },
                      "wsSettings": {
                          "path": params_json.get('path'),
                          "headers": {
                              "Host": params_json.get('host')
                          }
                      }
                  }, }
        return config
    except Exception as e:
        logger.error(e)
        return None


def get_share_links(return_content):
    share_links = b64decode(return_content).decode('utf-8').splitlines()
    return share_links


def read_content(share_links) -> list:
    link_with_config = []
    for item in share_links:
        for link in item.get('share_links'):
            url_split = urlsplit(link)
            protocol = url_split.scheme
            if protocol in VALID_PROTOCOL:
                config = eval('read_' + protocol)(url_split)
                tmp = {'source_url': item.get('source_url'), 'share_link': link, 'config': config}
                link_with_config.append(tmp)
            else:
                logger.info('protocol %s not supported' % protocol)
    return link_with_config


def set_config(config: dict, config_file='/usr/local/etc/v2ray/config.json'):
    logger.info('set config and restart v2ray')
    if config:
        protocol = config.get('protocol')
        temp = template.get(protocol)
        outbounds = temp.get('outbounds')
        proxy_tag = outbounds[0]
        proxy_tag['protocol'] = protocol
        proxy_tag['settings'] = config.get('settings')
        proxy_tag['streamSettings'] = config.get('streamSettings')
        output = json.dumps(temp, indent=True, sort_keys=True)
        with open(config_file, 'w') as f:
            f.write(output)
        start_v2ray_cmd = 'v2ray -config /usr/local/etc/v2ray/config.json>/dev/null 2>&1 &'
        stop_v2ray_cmd = "kill -9 `ps -ef | grep v2ray | grep -v grep | awk '{print $2}'`"
        os.system(stop_v2ray_cmd)
        os.system(start_v2ray_cmd)
        time.sleep(WAIT_RESTART)


def get_web_speed():
    logger.info('testing web speed ...')
    start = time.time()
    socks.setdefaultproxy(socks.SOCKS5, '127.0.0.1', 2333)
    socket.socket = socks.socksocket
    url = 'http://www.google.com'
    try:
        requests.get(url, timeout=TIME_LIMIT)
    except Exception as e:
        logger.error(e)
        return 10
    end = time.time()
    return end - start


def get_download_speed():
    logger.info('testing download speed ...')
    cmd = 'curl -m' + str(
        TIME_LIMIT) + ' -x socks5://127.0.0.1:2333 -Lo /dev/null -skw "%{speed_download}\n" http://cachefly.cachefly.net/10mb.test'
    p = os.popen(cmd)
    result = p.readlines()
    if isinstance(result, list):
        download_speed = result[0].replace('\n', '')
        return float(download_speed)
    return 10


def get_best_config(share_links) -> dict:
    link_with_config = read_content(share_links)
    best_links = {}
    total_config_number = len(link_with_config)
    for i in range(total_config_number):
        tmp = link_with_config[i]
        logger.info('testing config %s/%s' % (i, total_config_number))
        set_config(tmp.get('config'))
        web_speed = get_web_speed()
        if web_speed < WEB_SPEED:
            logger.info('web_speed--> %s' % web_speed)
            download_speed = get_download_speed()
            status = 1
            if download_speed > DOWNLOAD_SPEED:
                logger.info('download_speed--> %s' % download_speed)
                logger.info('find a fast link, add to best_links--> %s' % tmp.get('share_link'))
                best_links[tmp.get('share_link')] = download_speed
                status = 0
            SubscriptionModel(
                link=tmp.get('share_link'),
                config=tmp.get('config'),
                source=tmp.get('source_url'),
                web_speed=web_speed,
                download_speed=download_speed,
                status=status
            ).save()
    return best_links


def gen_subscribe(urls, n):
    start_time = time.strftime("%m-%d %H:%M", time.localtime())
    share_links = []
    for url in urls:
        tmp_links = get_share_links(get_return_content(url))
        tmp_dict = {'source_url': url, 'share_links': tmp_links}
        share_links.append(tmp_dict)

    best_links = get_best_config(share_links)
    sorted_links = sorted(best_links.items(), key=lambda item: item[1], reverse=True)[:n]
    end_time = time.strftime("%m-%d %H:%M", time.localtime())
    link_str = '%s\n' % gen_update_time('start:%s;end:%s' % (start_time, end_time)) + '\n'.join(
        link[0] for link in sorted_links)
    link_b64 = base64.b64encode(link_str.encode('utf-8'))
    return link_b64


def set_default_v2ray():
    logger.info('set_default_v2ray')
    set_config(bwg)


def get_return_content(url):
    socks.setdefaultproxy(socks.SOCKS5, '127.0.0.1', 2333)
    socket.socket = socks.socksocket
    if 'api.github.com' in url:
        tmp = requests.get(url).json().get('content')
        return b64decode(tmp).decode('utf-8')
    return urlopen(url).read()


def main(link_num=10):
    set_default_v2ray()
    c = gen_subscribe(ONLINE_URLS, link_num)
    logger.info(c)


if __name__ == '__main__':
    main()
