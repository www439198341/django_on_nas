import base64
import json
import time

from django.db.models import Avg
from django.http import HttpResponse

from better_v2ray.get_link import get_web_speed, set_config, WEB_SPEED, get_download_speed, \
    set_default_v2ray, get_share_links, get_return_content, get_best_config, print_with_color
from better_v2ray.models import SubscriptionModel
# Create your views here.
from local_settings import ONLINE_URLS


def gen_update_time():
    json_content = {'v': '2', 'ps': '更新于:%s' % time.strftime("%m-%d %H:%M", time.localtime()), 'add': 'Flynn',
                    'port': '0', 'id': '6a3bcc08-9c77-4c02-844b-4a694c4f2fea', 'aid': '0', 'net': 'tcp', 'type': 'none',
                    'host': '', 'path': '', 'tls': '', 'sni': ''}
    str_content = json.dumps(json_content)
    link_with_update_time = str(b'vmess://' + base64.b64encode(str_content.encode('utf-8')), encoding='utf-8')
    return link_with_update_time


def get_subscription_link(request):
    num = request.GET.get('num')
    quality = request.GET.get('quality')
    if not num:
        num = 10
    else:
        num = int(num)
    if quality:
        quality = int(quality)
    else:
        quality = 0
    print_with_color('green', 'num-->%s' % num)
    print_with_color('green', 'quality-->%s' % quality)
    configs = SubscriptionModel.objects.filter(status__lte=quality).order_by('-download_speed')[:num]

    link_str = '%s\n' % gen_update_time() + '\n'.join(config.link for config in configs)
    link_b64 = base64.b64encode(link_str.encode('utf-8'))
    return HttpResponse(link_b64)


def renew():
    """
    对配置重新测速，并更新信息
    :return:
    """
    configs = SubscriptionModel.objects.filter(status__in=(0, 1))
    avg_dl_speed = SubscriptionModel.objects.filter(status=0).aggregate(Avg('download_speed')).get(
        'download_speed__avg') or 0
    for index, config in enumerate(configs):
        print_with_color('red', 'testing config %s/%s' % (index, len(configs)))
        set_config(eval(config.config))
        before_status = config.status
        web_speed = get_web_speed()
        if web_speed < WEB_SPEED:
            config.web_speed = web_speed
            download_speed = get_download_speed()
            if download_speed > avg_dl_speed:
                config.download_speed = (config.download_speed + download_speed) / 2
                config.status = 0
                print_with_color('green', 'updated speed with download_speed %s' % config.download_speed)
            else:
                config.status = 1
        elif web_speed == 10:
            config.status = 2
        else:
            config.status = 1
        # 根据状态前后变化，进行不同颜色的打印
        if before_status == 0 and config.status == 1:
            print_with_color('yellow', 'config updated set status 1')
        elif before_status == 0 and config.status == 2:
            print_with_color('red', 'config updated set status 2')
        elif before_status == 1 and config.status == 0:
            print_with_color('green', 'config updated set status 0')
        elif before_status == 1 and config.status == 2:
            print_with_color('red', 'config updated set status 2')
        config.save()


def is_renew():
    configs = SubscriptionModel.objects.filter(status=0)
    if len(configs) < 10 or time.localtime().tm_hour == 1:
        return True
    return False


def renew_subscription_link(request):
    """
    读取并测试数据库中已有的配置，更新其速度/或删除配置，若配置数不足10条，则从网络上获取并更新入库
    """
    renew()

    if is_renew():
        set_default_v2ray()
        share_links = []
        for url in ONLINE_URLS:
            tmp_links = get_share_links(get_return_content(url))
            tmp_dict = {'source_url': url, 'share_links': tmp_links}
            share_links.append(tmp_dict)
        get_best_config(share_links)
    return HttpResponse(b'done')
