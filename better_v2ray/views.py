import base64
import json
import os
import time

from django.db.models import Avg
from django.http import HttpResponse, FileResponse

from better_v2ray.convert2clash import get_proxies, get_default_config, add_proxies_to_model, save_config
from better_v2ray.get_link import get_web_speed, set_config, WEB_SPEED, get_download_speed, \
    set_default_v2ray, get_share_links, get_return_content, get_best_config
from better_v2ray.models import SubscriptionModel
# Create your views here.
from django_on_nas.settings import logger, BASE_DIR
from local_settings import ONLINE_URLS, SUB_URL


def gen_update_time():
    json_content = {'v': '2', 'ps': '更新于:%s' % time.strftime("%m-%d %H:%M", time.localtime()), 'add': 'Flynn',
                    'port': '0', 'id': '6a3bcc08-9c77-4c02-844b-4a694c4f2fea', 'aid': '0', 'net': 'tcp', 'type': 'none',
                    'host': '', 'path': '', 'tls': '', 'sni': ''}
    str_content = json.dumps(json_content)
    link_with_update_time = str(b'vmess://' + base64.b64encode(str_content.encode('utf-8')), encoding='utf-8')
    return link_with_update_time


def get_subscription_link(request):
    num = int(request.GET.get('num', '10'))
    quality = int(request.GET.get('quality', '0'))
    target = request.GET.get('target', '')
    logger.info('num-->%s, quality-->%s' % (num, quality))
    configs = SubscriptionModel.objects.filter(status__lte=quality).order_by('-download_speed')[:num]
    if target == 'clash':
        sub_url = SUB_URL % (num, quality)
        # 输出路径
        config_path = os.path.join(BASE_DIR, 'template.yaml')
        output_path = os.path.join(BASE_DIR, 'output.yaml')
        node_list = get_proxies(sub_url)
        default_config = get_default_config(config_path)
        final_config = add_proxies_to_model(node_list, default_config)
        save_config(output_path, final_config)
        logger.info(f'文件已导出至 {output_path}')
        file = open(output_path, 'rb')
        response = FileResponse(file)
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = 'attachment;filename="mine-online.yml"'
        return response
    else:
        link_str = '%s\n' % gen_update_time() + '\n'.join(config.link for config in configs)
        # link_str = '\n'.join(config.link for config in configs)
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
        logger.info('testing config %s/%s' % (index, len(configs)))
        set_config(eval(config.config))
        before_status = config.status
        web_speed = get_web_speed()
        if web_speed < WEB_SPEED:
            config.web_speed = web_speed
            download_speed = get_download_speed()
            if download_speed > avg_dl_speed:
                config.download_speed = (config.download_speed + download_speed) / 2
                config.status = 0
                logger.info('updated speed with download_speed %s' % config.download_speed)
            else:
                config.status = 1
        elif web_speed == 10:
            config.status = 2
        else:
            config.status = 1
        # 根据状态前后变化，进行不同颜色的打印
        logger.info('config updated set status %s' % config.status)
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
