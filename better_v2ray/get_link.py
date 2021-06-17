import hashlib
import json
import os
import subprocess
import time
from base64 import b64decode
from urllib.parse import urlsplit

import requests
from django.db.models import Avg

from better_v2ray.models import SubscriptionModel
from django_on_nas.settings import logger
from local_settings import template, WAIT_RESTART, TIME_LIMIT, WEB_SPEED, VALID_PROTOCOL, DELAY_TESTING_URL, \
    DOWNLOAD_TEST_URL, bwg


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
    cmd = "curl -m 1 -o /dev/null -s -w '%{time_total}\n' " + DELAY_TESTING_URL
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    out, err = p.communicate()
    if p.returncode == 0:
        web_speed = str(out, encoding='utf-8').replace('\n', '')
        print('web_speed-->{}'.format(web_speed))
        try:
            web_speed = float(web_speed)
            logger.info('到{}的延迟为{:.2f}ms'.format(DELAY_TESTING_URL, web_speed * 1000))
            return web_speed
        except ValueError:
            return 10
    return 10


def get_download_speed():
    logger.info('testing download speed ...')
    cmd = 'curl -m' + str(
        TIME_LIMIT) + ' -x socks5://127.0.0.1:2333 -Lo /dev/null -skw "%{speed_download}\n" ' + DOWNLOAD_TEST_URL
    p = os.popen(cmd)
    result = p.readlines()
    if isinstance(result, list):
        download_speed = result[0].replace('\n', '')
        logger.info('测试%s下载速度为%.2fMb/s' % (DOWNLOAD_TEST_URL, float(download_speed) / 1e6))
        return float(download_speed)
    logger.info('测试下载超时')
    return 10


def get_config(share_links):
    def get_md5(raw_str):
        m = hashlib.md5()
        m.update(raw_str.encode())
        return m.hexdigest()

    # insert config info into db. set status = 3(not tested)
    link_with_config = read_content(share_links)
    logger.info('共获得%s个配置' % len(link_with_config))
    count = 0
    for item in link_with_config:
        if item and item.get('config'):
            md5_info = get_md5(json.dumps(item.get('config')))
            records = SubscriptionModel.objects.filter(md5_info=md5_info)
            if len(records) == 0:  # 如果没有相同md5的数据，则新数据入库
                SubscriptionModel(
                    source=item.get('source_url'),
                    link=item.get('share_link'),
                    config=item.get('config'),
                    status=3,
                    web_speed=9,
                    download_speed=0,
                    md5_info=md5_info
                ).save()
                logger.info('数据入库%s' % item)
            else:  # 否则更其起状态为3/web_speed为9/download_speed为0
                record = SubscriptionModel.objects.get(md5_info=md5_info)
                record.status = 3
                record.web_speed = 9
                record.download_speed = 0
                record.save()
            count += 1
    logger.info('共入库%s条数据' % count)
    return count


def renew(target_status: tuple, avg_status: tuple = (0,)):
    """
    对配置重新测速，并更新信息
    :return:
    """
    configs = SubscriptionModel.objects.filter(status__in=target_status)
    avg_dl_speed = SubscriptionModel.objects.filter(status__in=avg_status).aggregate(Avg('download_speed')).get(
        'download_speed__avg') or 0
    for index, config in enumerate(configs):
        logger.info('测试配置%s, 当前进度%s/%s' % (config, index, len(configs)))
        set_config(eval(config.config))
        web_speed = get_web_speed()
        if web_speed < WEB_SPEED:
            config.web_speed = web_speed
            download_speed = get_download_speed()
            if download_speed > avg_dl_speed:
                logger.info('下载速度%s大于平均下载速度%s，发现优质链接' % (download_speed, avg_dl_speed))
                config.download_speed = (config.download_speed + download_speed) / 2
                config.status = 0
            else:
                logger.info('下载速度%s小于平均下载速度%s，发现可用链接' % (download_speed, avg_dl_speed))
                config.status = 1
        elif web_speed == 10:
            logger.info('网络延迟测试超时，链接不可用')
            config.status = 2
        else:
            logger.info('网络延迟%s大于预设阀值%s，发现可用链接' % (web_speed, WEB_SPEED))
            config.status = 1
        logger.info('config updated set status %s' % config.status)
        config.save()


def get_share_links(url):
    if 'api.github.com' in url:
        tmp = requests.get(url).json().get('content')
        b_return = b64decode(tmp).decode('utf-8')
    else:
        b_return = requests.get(url).text
    return b64decode(b_return).decode('utf-8').splitlines()


def set_default_v2ray():
    logger.info('set_default_v2ray')
    set_config(bwg)
