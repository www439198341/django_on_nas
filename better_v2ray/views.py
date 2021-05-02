import base64
import json
import os
import time

from django.http import HttpResponse, FileResponse

from better_v2ray.convert2clash import get_proxies, get_default_config, add_proxies_to_model, save_config
from better_v2ray.get_link import get_share_links, get_config, renew
from better_v2ray.models import SubscriptionModel
from django_on_nas.settings import logger, BASE_DIR
from local_settings import ONLINE_URLS, SUB_URL


def gen_update_time():
    json_content = {'v': '2', 'ps': '更新于:%s' % time.strftime("%m-%d %H:%M", time.localtime()), 'add': 'Flynn',
                    'port': '3652', 'id': '6a3bcc08-9c77-4c02-844b-4a694c4f2fea', 'aid': '0', 'net': 'tcp',
                    'type': 'none',
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
        link_b64 = base64.b64encode(link_str.encode('utf-8'))
        return HttpResponse(link_b64)


def is_renew():
    configs = SubscriptionModel.objects.filter(status=0)
    if len(configs) < 5:
        return True
    return False


def is_download():
    if time.localtime().tm_hour % 2 == 1:
        return True
    return False


def renew_subscription_link(request):
    """
    读取并测试数据库中已有的配置，更新其速度/或删除配置，若配置数不足10条，则从网络上获取并更新入库
    """

    if is_download():
        share_links = []
        for url in ONLINE_URLS:
            logger.info('解析订阅地址%s' % url)
            tmp_links = get_share_links(url)
            tmp_dict = {'source_url': url, 'share_links': tmp_links}
            share_links.append(tmp_dict)
        get_config(share_links)
        renew(target_status=(0,), avg_status=(0, 1))

    if is_renew():
        renew((0, 1, 3))

    return HttpResponse(b'done')
