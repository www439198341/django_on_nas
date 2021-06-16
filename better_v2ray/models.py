from django.db import models

# Create your models here.
from django.utils import timezone


class SubscriptionModel(models.Model):
    link = models.CharField(max_length=1000, verbose_name='链接')
    config = models.CharField(max_length=2000, verbose_name='配置')
    web_speed = models.FloatField(verbose_name='网页测速')
    download_speed = models.FloatField(verbose_name='下载测速')
    status = models.IntegerField(verbose_name='状态', default=0, help_text='链接状态.0-高速;1-低速;2-连续低速;3-未测试')
    source = models.CharField(max_length=1000, verbose_name='订阅来源')
    add_time = models.DateTimeField(default=timezone.now, verbose_name='添加时间')
    modify_time = models.DateTimeField(auto_now=True, verbose_name='修改时间')
    md5_info = models.CharField(max_length=100, verbose_name='配置信息md5值')

    class Meta:
        verbose_name = '配置信息'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.link


class Record(models.Model):
    """
    更新记录。
    """
    start_time = models.DateTimeField(verbose_name='更新开始时间')
    end_time = models.DateTimeField(verbose_name='更新结束时间')
    add_time = models.DateTimeField(default=timezone.now, verbose_name='添加时间')
    is_download = models.BooleanField(verbose_name='是否从网络更新节点')
    is_renew = models.BooleanField(verbose_name='是否更新现有节点')
    better_node_count = models.IntegerField(verbose_name='优质节点数')
    normal_node_count = models.IntegerField(verbose_name='普通节点数')
    dead_node_count = models.IntegerField(verbose_name='不可用节点数')

    class Meta:
        verbose_name = '节点更新记录'
        verbose_name_plural = verbose_name

    def __str__(self):
        return str(self.id)
