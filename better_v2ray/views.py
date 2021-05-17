import base64
import json
import os
import time

from django.http import HttpResponse, FileResponse

from better_v2ray.convert2clash import get_proxies, get_default_config, add_proxies_to_model, save_config
from better_v2ray.get_link import get_share_links, get_config, renew, set_default_v2ray
from better_v2ray.models import SubscriptionModel
from django_on_nas.settings import logger, BASE_DIR
from local_settings import ONLINE_URLS, SUB_URL, GOOD_LINK_NUM

output_path = os.path.join(BASE_DIR, 'output.yaml')


def gen_update_time(return_type='base64'):
    count = SubscriptionModel.objects.filter(status=0).count()
    if return_type == 'json':
        json_content = {'name': '更新:%s,可用%s' % (time.strftime("%m-%d %H:%M", time.localtime()), count), 'type': 'ss',
                        'server': 'does.not.exist', 'port': '886', 'cipher': 'aes-256-gcm', 'password': 'never need'}
        return json_content
    else:
        json_content = {'v': '2', 'ps': '更新:%s,可用%s' % (time.strftime("%m-%d %H:%M", time.localtime()), count),
                        'add': 'Flynn', 'port': '3652', 'id': '6a3bcc08-9c77-4c02-844b-4a694c4f2fea', 'aid': '0',
                        'net': 'tcp', 'type': 'none', 'host': '', 'path': '', 'tls': '', 'sni': ''}
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
        set_yaml_file(num, quality)
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
    if len(configs) < GOOD_LINK_NUM:
        return True
    return False


def is_download():
    if time.localtime().tm_hour % 2 == 1:
        return True
    return False


def set_yaml_file(num, quality):
    sub_url = SUB_URL % (num, quality)
    # 输出路径
    config_path = os.path.join(BASE_DIR, 'template.yaml')
    node_list = get_proxies(sub_url)
    logger.info('node_list, %s' % node_list)
    default_config = get_default_config(config_path)
    final_config = add_proxies_to_model(node_list, default_config)
    save_config(output_path, final_config)
    logger.info(f'文件已导出至 {output_path}')


def renew_subscription_link(request):
    """
    读取并测试数据库中已有的配置，更新其速度/或删除配置，若配置数不足10条，则从网络上获取并更新入库
    """

    if is_download():
        set_default_v2ray()
        share_links = []
        for url in ONLINE_URLS:
            logger.info('解析订阅地址%s' % url)
            tmp_links = get_share_links(url)
            tmp_dict = {'source_url': url, 'share_links': tmp_links}
            share_links.append(tmp_dict)
        count = get_config(share_links)
        if count < 10:  # 如果获得到新链接小于10个，即所有链接都已有数据库记录，无法获得新链接，则更新全部已有链接信息。
            renew(target_status=(0, 1, 2))
        else:
            renew(target_status=(0,), avg_status=(0, 1))

    if is_renew():
        renew((0, 1, 3))

    # 生成配置文件并送到远端保存
    set_yaml_file(100, 1)

    return HttpResponse(b'done')
